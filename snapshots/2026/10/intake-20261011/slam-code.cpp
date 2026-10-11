/*
 * slam_toolbox_web_node
 *
 * Web-based 3D SLAM visualization for slam_toolbox (mirrors drtabmap/rtabmap_web).
 *
 * A standalone rclcpp node that:
 *   - subscribes to /scan, /odom (inputs) and /map, /pose (outputs);
 *   - projects /scan and /odom into the map frame via tf2;
 *   - colorizes the /map OccupancyGrid into a PNG (rviz2 palette);
 *   - serves an HTML page over HTTP and pushes PNG + JSON state over WebSocket
 *     (Boost.Beast), so a browser shows the map + scan + trajectory + pose.
 *
 * Frame types (WebSocket binary, little-endian where applicable):
 *   byte0 = 0  -> colorized map PNG
 *   byte0 = 1  -> UTF-8 JSON state
 *
 * Licensed under the Apache License, Version 2.0.
 */

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <nav_msgs/msg/occupancy_grid.hpp>
#include <geometry_msgs/msg/pose_with_covariance_stamped.hpp>
#include <builtin_interfaces/msg/time.hpp>
#include <slam_toolbox/msg/loop_closure_event.hpp>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>
#include <tf2/time.h>
#include <tf2/utils.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <tf2_msgs/msg/tf_message.hpp>

#include <boost/asio/ip/tcp.hpp>
#include <boost/beast/core.hpp>
#include <boost/beast/http.hpp>
#include <boost/beast/websocket.hpp>

#include <opencv2/opencv.hpp>

#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace slam_toolbox_web {

namespace asio = boost::asio;
namespace beast = boost::beast;
namespace http = beast::http;
namespace websocket = beast::websocket;
using tcp = asio::ip::tcp;

// WebSocket binary frame types
constexpr uint8_t kFrameTypeMap = 0;   // colorized 2D grid map image (PNG)
constexpr uint8_t kFrameTypeJSON = 1;  // JSON state (map meta, scan, trajectory, pose)

/**
 * @brief Thread-safe shared state between the viewer node and the WS server.
 */
struct SharedVizState {
  using Frame = std::vector<uint8_t>;
  using FramePtr = std::shared_ptr<const Frame>;

  void set_map(Frame data) {
    auto next = std::make_shared<const Frame>(std::move(data));
    std::lock_guard<std::mutex> lock(mtx_);
    map_frame_ = std::move(next);
    map_seq_++;
  }

  void set_json(std::string json) {
    auto next = std::make_shared<const std::string>(std::move(json));
    std::lock_guard<std::mutex> lock(mtx_);
    json_frame_ = std::move(next);
    json_seq_++;
  }

  std::pair<FramePtr, uint64_t> get_map() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return {map_frame_, map_seq_};
  }

  std::pair<std::shared_ptr<const std::string>, uint64_t> get_json() const {
    std::lock_guard<std::mutex> lock(mtx_);
    return {json_frame_, json_seq_};
  }

private:
  mutable std::mutex mtx_;
  FramePtr map_frame_;
  std::shared_ptr<const std::string> json_frame_;
  uint64_t map_seq_{0};
  uint64_t json_seq_{0};
};

/**
 * @brief Boost.Beast WebSocket server (HTTP + WS), adapted from rtabmap_web.
 */
class WebServer {
public:
  WebServer(std::string host, uint16_t port, std::string index_html_path,
            std::shared_ptr<SharedVizState> state)
      : host_(std::move(host)), port_(port), index_html_path_(std::move(index_html_path)),
        state_(std::move(state)) {}

  ~WebServer() { stop(); }

  WebServer(const WebServer &) = delete;
  WebServer &operator=(const WebServer &) = delete;

  void start() {
    if (running_.exchange(true)) return;
    server_thread_ = std::thread(&WebServer::run, this);
  }

  void stop() {
    if (!running_.exchange(false)) return;
    try {
      boost::asio::io_context ctx;
      boost::asio::ip::tcp::socket s(ctx);
      s.connect(boost::asio::ip::tcp::endpoint(boost::asio::ip::make_address("127.0.0.1"), port_));
    } catch (...) {}
    if (server_thread_.joinable()) server_thread_.join();
  }

private:
  static std::string read_file(const std::string &path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return "";
    return std::string(std::istreambuf_iterator<char>(f), {});
  }

  void ws_session(tcp::socket socket, http::request<http::string_body> req) {
    try {
      websocket::stream<tcp::socket> ws(std::move(socket));
      ws.set_option(websocket::stream_base::timeout::suggested(beast::role_type::server));
      ws.binary(true);
      ws.accept(req);

      uint64_t last_map_seq = 0, last_json_seq = 0;
      auto sleep = std::chrono::milliseconds(33);  // ~30fps

      for (;;) {
        auto [map, map_seq] = state_->get_map();
        if (map && map_seq != last_map_seq) {
          std::vector<uint8_t> frame;
          frame.push_back(kFrameTypeMap);
          frame.insert(frame.end(), map->begin(), map->end());
          beast::error_code ec;
          ws.write(asio::buffer(frame), ec);
          if (ec) break;
          last_map_seq = map_seq;
        }

        auto [json, json_seq] = state_->get_json();
        if (json && json_seq != last_json_seq) {
          std::vector<uint8_t> frame;
          frame.push_back(kFrameTypeJSON);
          frame.insert(frame.end(), json->begin(), json->end());
          beast::error_code ec;
          ws.write(asio::buffer(frame), ec);
          if (ec) break;
          last_json_seq = json_seq;
        }

        std::this_thread::sleep_for(sleep);
      }
    } catch (...) {
      // Browser closed, expected
    }
  }

  void http_session(tcp::socket socket, std::string html, std::string three_js) {
    try {
      beast::flat_buffer buf;
      http::request<http::string_body> req;
      http::read(socket, buf, req);

      std::string target(req.target());
      const auto qpos = target.find('?');
      if (qpos != std::string::npos) target = target.substr(0, qpos);

      if (websocket::is_upgrade(req) && target == "/ws") {
        ws_session(std::move(socket), std::move(req));
        return;
      }

      http::response<http::string_body> res;
      if (target == "/" || target == "/index.html") {
        res.result(http::status::ok);
        res.set(http::field::content_type, "text/html; charset=utf-8");
        res.body() = std::move(html);
      } else if (target == "/three.min.js") {
        res.result(http::status::ok);
        res.set(http::field::content_type, "application/javascript");
        res.set(http::field::cache_control, "max-age=3600");
        res.body() = std::move(three_js);
      } else {
        res.result(http::status::not_found);
        res.set(http::field::content_type, "text/plain");
        res.body() = "Not found";
      }
      res.set(http::field::server, "slam_toolbox_web");
      res.keep_alive(false);
      res.prepare_payload();

      beast::error_code ec;
      http::write(socket, res, ec);
      socket.shutdown(tcp::socket::shutdown_send, ec);
    } catch (...) {
      // Ignore short-lived connections
    }
  }

  void run() {
    try {
      auto html = read_file(index_html_path_);
      if (html.empty()) html = "<html><body><h1>web/index.html not found</h1></body></html>";
      // three.js lives next to index.html; serve it so the 3D scene can load.
      std::string three_js_path = index_html_path_;
      const auto slash = three_js_path.find_last_of('/');
      if (slash != std::string::npos) {
        three_js_path = three_js_path.substr(0, slash + 1) + "three.min.js";
      } else {
        three_js_path = "three.min.js";
      }
      auto three_js = read_file(three_js_path);
      asio::io_context ctx(1);
      auto addr = asio::ip::make_address(host_);
      tcp::acceptor acceptor(ctx);
      acceptor.open(addr.is_v6() ? tcp::v6() : tcp::v4());
      acceptor.set_option(asio::socket_base::reuse_address(true));
      acceptor.bind(tcp::endpoint(addr, port_));
      acceptor.listen(asio::socket_base::max_listen_connections);

      while (running_.load()) {
        tcp::socket socket(ctx);
        beast::error_code ec;
        acceptor.accept(socket, ec);
        if (!running_.load()) break;
        if (ec) continue;
        std::thread(&WebServer::http_session, this, std::move(socket), html, three_js).detach();
      }
    } catch (...) {
      running_.store(false);
    }
  }

  std::string host_;
  uint16_t port_;
  std::string index_html_path_;
  std::shared_ptr<SharedVizState> state_;

  std::atomic<bool> running_{false};
  std::thread server_thread_;
};

/// FPS tracker using a 1-second sliding window (robust to bursts).
struct FpsTracker {
  std::chrono::steady_clock::time_point window_start;
  int count = 0;
  double fps = 0;
  void tick() {
    auto now = std::chrono::steady_clock::now();
    if (window_start.time_since_epoch().count() == 0) window_start = now;
    count++;
    double elapsed = std::chrono::duration<double>(now - window_start).count();
    if (elapsed >= 1.0) {
      fps = count / elapsed;
      count = 0;
      window_start = now;
    }
  }
};

// Minimal JSON string escaper (topic/frame names shouldn't contain quotes/backslashes).
static std::string json_escape(const std::string &s) {
  std::string out;
  out.reserve(s.size());
  for (char c : s) {
    switch (c) {
      case '"': out += "\\\""; break;
      case '\\': out += "\\\\"; break;
      default: out += c;
    }
  }
  return out;
}

// Colorize a nav_msgs::msg::OccupancyGrid into a BGR image using the rviz2 "Map"
// palette (unknown = gray 150, free = white, occupied = black) and PNG-encode it.
static std::vector<uint8_t> colorize_grid(const nav_msgs::msg::OccupancyGrid &grid) {
  int w = static_cast<int>(grid.info.width);
  int h = static_cast<int>(grid.info.height);
  if (w <= 0 || h <= 0) return {};
  if (grid.data.size() < static_cast<size_t>(w) * static_cast<size_t>(h)) return {};

  cv::Mat img(h, w, CV_8UC3);
  const int8_t *src = grid.data.data();
  for (int r = 0; r < h; ++r) {
    cv::Vec3b *row = img.ptr<cv::Vec3b>(r);
    const int8_t *line = src + static_cast<size_t>(r) * w;
    for (int c = 0; c < w; ++c) {
      int v = static_cast<int>(line[c]);
      unsigned char g;
      if (v < 0)            g = 150;                                      // unknown (mid grey)
      else if (v >= 100)    g = 0;                                        // occupied
      else                  g = static_cast<unsigned char>(255 - v * 2.55); // free -> white ramp
      row[c] = cv::Vec3b(g, g, g);
    }
  }

  std::vector<uint8_t> png;
  std::vector<int> params = {cv::IMWRITE_PNG_COMPRESSION, 1};
  cv::imencode(".png", img, png, params);
  return png;
}

/**
 * @brief The slam_toolbox web visualization node.
 */
class SlamToolboxWebNode : public rclcpp::Node {
public:
  explicit SlamToolboxWebNode(const rclcpp::NodeOptions &options = rclcpp::NodeOptions())
      : Node("slam_toolbox_web", options) {

    this->declare_parameter<std::string>("scan_topic", "/scan");
    this->declare_parameter<std::string>("odom_topic", "/odom");
    this->declare_parameter<std::string>("map_topic", "/map");
    this->declare_parameter<std::string>("pose_topic", "/pose");
    this->declare_parameter<std::string>("loop_closure_topic", "slam_toolbox/loop_closure_event");
    this->declare_parameter<std::string>("map_frame", "map");
    this->declare_parameter<std::string>("odom_frame", "odom");
    this->declare_parameter<std::string>("base_frame", "base_link");
    this->declare_parameter<std::string>("host", "0.0.0.0");
    this->declare_parameter<int>("port", 9992);
    this->declare_parameter<double>("publish_fps", 15.0);
    this->declare_parameter<std::string>("web_dir", "");

    scan_topic_ = this->get_parameter("scan_topic").as_string();
    odom_topic_ = this->get_parameter("odom_topic").as_string();
    map_topic_ = this->get_parameter("map_topic").as_string();
    pose_topic_ = this->get_parameter("pose_topic").as_string();
    loop_closure_topic_ = this->get_parameter("loop_closure_topic").as_string();
    map_frame_ = this->get_parameter("map_frame").as_string();
    odom_frame_ = this->get_parameter("odom_frame").as_string();
    base_frame_ = this->get_parameter("base_frame").as_string();
    host_ = this->get_parameter("host").as_string();
    port_ = this->get_parameter("port").as_int();
    publish_fps_ = this->get_parameter("publish_fps").as_double();

    viz_state_ = std::make_shared<SharedVizState>();

    // tf2 buffer with a dedicated thread so the transform cache is pruned and
    // incoming /tf is serviced without blocking the executor.
    tf_buffer_ = std::make_unique<tf2_ros::Buffer>(this->get_clock());
    tf_buffer_->setUsingDedicatedThread(true);
    tf_listener_ = std::make_unique<tf2_ros::TransformListener>(*tf_buffer_);

    // Reentrant callback group on a multi-threaded executor: the tf lookups can
    // briefly block, so let callbacks run concurrently.
    auto cb_group = this->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
    rclcpp::SubscriptionOptions sub_opt;
    sub_opt.callback_group = cb_group;

    // Display subscriptions use best_effort: a best_effort subscriber matches both
    // best_effort and reliable publishers (a reliable subscriber would drop a
    // best_effort publisher like the TurtleBot4 bag's /odom). Over UDPv4 this also
    // keeps the reader out of FastDDS reliable flow control.
    scan_sub_ = this->create_subscription<sensor_msgs::msg::LaserScan>(
        scan_topic_, rclcpp::QoS(10).best_effort(),
        std::bind(&SlamToolboxWebNode::scan_callback, this, std::placeholders::_1), sub_opt);
    odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>(
        odom_topic_, rclcpp::QoS(10).best_effort(),
        std::bind(&SlamToolboxWebNode::odom_callback, this, std::placeholders::_1), sub_opt);
    // /map is transient_local (latched) from slam_toolbox; transient_local lets a
    // late-joining web node receive the current map immediately.
    map_sub_ = this->create_subscription<nav_msgs::msg::OccupancyGrid>(
        map_topic_, rclcpp::QoS(1).reliable().transient_local(),
        std::bind(&SlamToolboxWebNode::map_callback, this, std::placeholders::_1), sub_opt);
    pose_sub_ = this->create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>(
        pose_topic_, rclcpp::QoS(1).best_effort(),
        std::bind(&SlamToolboxWebNode::pose_callback, this, std::placeholders::_1), sub_opt);

    // Direct /tf + /tf_static subscriptions only to classify which frames came
    // from which topic (tf2's Buffer does not expose that). Poses are still
    // looked up through tf_buffer_. /tf_static is transient_local (latched), so a
    // late-joining web node still learns the static frames.
    tf_sub_ = this->create_subscription<tf2_msgs::msg::TFMessage>(
        "/tf", rclcpp::QoS(10).best_effort(),
        std::bind(&SlamToolboxWebNode::tf_callback, this, std::placeholders::_1), sub_opt);
    tf_static_sub_ = this->create_subscription<tf2_msgs::msg::TFMessage>(
        "/tf_static", rclcpp::QoS(1).reliable().transient_local(),
        std::bind(&SlamToolboxWebNode::tf_static_callback, this, std::placeholders::_1), sub_opt);
    // slam_toolbox publishes one LoopClosureEvent (a bare stamp) each time it
    // accepts a loop closure. best_effort matches the reliable publisher fine.
    loop_closure_sub_ = this->create_subscription<slam_toolbox::msg::LoopClosureEvent>(
        loop_closure_topic_, rclcpp::QoS(10).best_effort(),
        std::bind(&SlamToolboxWebNode::loop_closure_callback, this, std::placeholders::_1), sub_opt);

    auto period = std::chrono::milliseconds(static_cast<int>(1000.0 / publish_fps_));
    timer_ = this->create_wall_timer(period, [this]() {
      auto json = build_json();
      if (!json.empty()) viz_state_->set_json(json);
    }, cb_group);

    std::string web_dir = this->get_parameter("web_dir").as_string();
    if (web_dir.empty()) web_dir = "index.html";
    server_ = std::make_shared<WebServer>(host_, port_, web_dir, viz_state_);
    server_->start();

    RCLCPP_INFO(this->get_logger(), "slam_toolbox_web started on http://%s:%d", host_.c_str(), port_);
    RCLCPP_INFO(this->get_logger(), "  scan: %s, odom: %s, map: %s, pose: %s -> frame: %s",
                scan_topic_.c_str(), odom_topic_.c_str(), map_topic_.c_str(),
                pose_topic_.c_str(), map_frame_.c_str());
  }

  ~SlamToolboxWebNode() override {
    if (server_) server_->stop();
  }

private:
  // Convert a builtin_interfaces Time to a tf2::TimePoint.
  static tf2::TimePoint to_tf2_time(const builtin_interfaces::msg::Time &t) {
    return tf2::timeFromSec(static_cast<double>(t.sec) + t.nanosec * 1e-9);
  }

  void scan_callback(const sensor_msgs::msg::LaserScan::SharedPtr scan) {
    scan_fps_.tick();
    try {
      auto tf = tf_buffer_->lookupTransform(map_frame_, scan->header.frame_id,
                                            to_tf2_time(scan->header.stamp),
                                            tf2::durationFromSec(0.2));
      const double yaw = tf2::getYaw(tf.transform.rotation);
      const double tx = tf.transform.translation.x;
      const double ty = tf.transform.translation.y;
      const double cy = std::cos(yaw), sy = std::sin(yaw);

      std::vector<double> pts;
      pts.reserve(scan->ranges.size() * 2);
      double angle = scan->angle_min;
      for (const auto &r : scan->ranges) {
        if (std::isfinite(r) && r >= scan->range_min && r <= scan->range_max) {
          const double lx = r * std::cos(angle);
          const double ly = r * std::sin(angle);
          pts.push_back(tx + cy * lx - sy * ly);
          pts.push_back(ty + sy * lx + cy * ly);
        }
        angle += scan->angle_increment;
      }
      std::lock_guard<std::mutex> lock(data_mtx_);
      scan_pts_ = std::move(pts);
      have_scan_ = true;
    } catch (const tf2::TransformException &) {
      // TF not ready yet; skip this scan.
    }
  }

  void odom_callback(const nav_msgs::msg::Odometry::SharedPtr odom) {
    odom_fps_.tick();
    // /odom is present, so keep the TF-based odometry fallback disabled.
    {
      std::lock_guard<std::mutex> lock(data_mtx_);
      have_odom_topic_ = true;
    }
    try {
      auto tf = tf_buffer_->lookupTransform(map_frame_, odom->header.frame_id,
                                            to_tf2_time(odom->header.stamp),
                                            tf2::durationFromSec(0.2));
      const double yaw = tf2::getYaw(tf.transform.rotation);
      const double tx = tf.transform.translation.x;
      const double ty = tf.transform.translation.y;
      const double cy = std::cos(yaw), sy = std::sin(yaw);

      const double bx = odom->pose.pose.position.x;
      const double by = odom->pose.pose.position.y;
      const double byaw = tf2::getYaw(odom->pose.pose.orientation);
      const double mx = tx + cy * bx - sy * by;
      const double my = ty + sy * bx + cy * by;
      const double myaw = yaw + byaw;

      std::lock_guard<std::mutex> lock(data_mtx_);
      odom_path_.push_back(mx);
      odom_path_.push_back(my);
      const size_t max_pts = 100000;
      if (odom_path_.size() > max_pts * 2) {
        odom_path_.erase(odom_path_.begin(), odom_path_.begin() + (max_pts / 2) * 2);
      }
      odom_pose_x_ = mx;
      odom_pose_y_ = my;
      odom_pose_yaw_ = myaw;
      have_odom_pose_ = true;
    } catch (const tf2::TransformException &) {
      // TF not ready yet; skip this odom sample.
    }
  }

  void map_callback(const nav_msgs::msg::OccupancyGrid::SharedPtr grid) {
    map_fps_.tick();
    {
      std::lock_guard<std::mutex> lock(data_mtx_);
      grid_ = *grid;
      have_grid_ = true;
    }
    auto png = colorize_grid(*grid);
    if (!png.empty()) viz_state_->set_map(std::move(png));
  }

  void pose_callback(const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr pose) {
    pose_fps_.tick();
    std::lock_guard<std::mutex> lock(data_mtx_);
    pose_topic_x_ = pose->pose.pose.position.x;
    pose_topic_y_ = pose->pose.pose.position.y;
    pose_topic_yaw_ = tf2::getYaw(pose->pose.pose.orientation);
    have_pose_topic_ = true;
    // /pose is already in the map frame; append it to the slam pose trajectory.
    pose_path_.push_back(pose_topic_x_);
    pose_path_.push_back(pose_topic_y_);
    const size_t max_pts = 100000;
    if (pose_path_.size() > max_pts * 2) {
      pose_path_.erase(pose_path_.begin(), pose_path_.begin() + (max_pts / 2) * 2);
    }
  }

  void loop_closure_callback(const slam_toolbox::msg::LoopClosureEvent::SharedPtr msg) {
    int count = 0;
    {
      std::lock_guard<std::mutex> lock(data_mtx_);
      loop_count_++;
      loop_last_ts_ = static_cast<double>(msg->stamp.sec) + msg->stamp.nanosec * 1e-9;
      count = loop_count_;
    }
    RCLCPP_INFO(this->get_logger(), "Loop closure detected (#%d)", count);
  }

  void tf_callback(const tf2_msgs::msg::TFMessage::SharedPtr msg) {
    bool have_odom_topic;
    {
      std::lock_guard<std::mutex> lock(data_mtx_);
      have_odom_topic = have_odom_topic_;
      for (const auto &t : msg->transforms) {
        tf_frames_.insert(t.child_frame_id);
        frame_parent_[t.child_frame_id] = t.header.frame_id;
      }
    }

    // TF-based odometry fallback: when the robot's odometry is only broadcast as a
    // transform (odom_frame -> base_frame on /tf) and there is no /odom topic
    // (e.g. the MIT Stata bag), draw the odometry trajectory from that transform,
    // projected into the map frame.
    if (have_odom_topic) return;
    for (const auto &t : msg->transforms) {
      if (t.header.frame_id != odom_frame_ || t.child_frame_id != base_frame_) continue;
      try {
        auto tf = tf_buffer_->lookupTransform(map_frame_, base_frame_,
                                              to_tf2_time(t.header.stamp),
                                              tf2::durationFromSec(0.2));
        const double tx = tf.transform.translation.x;
        const double ty = tf.transform.translation.y;
        const double yaw = tf2::getYaw(tf.transform.rotation);
        std::lock_guard<std::mutex> lock(data_mtx_);
        odom_path_.push_back(tx);
        odom_path_.push_back(ty);
        const size_t max_pts = 100000;
        if (odom_path_.size() > max_pts * 2) {
          odom_path_.erase(odom_path_.begin(), odom_path_.begin() + (max_pts / 2) * 2);
        }
        odom_pose_x_ = tx;
        odom_pose_y_ = ty;
        odom_pose_yaw_ = yaw;
        have_odom_pose_ = true;
      } catch (const tf2::TransformException &) {
        // map -> base_frame not (yet) available; skip this odometry sample.
      }
    }
  }

  void tf_static_callback(const tf2_msgs::msg::TFMessage::SharedPtr msg) {
    std::lock_guard<std::mutex> lock(data_mtx_);
    for (const auto &t : msg->transforms) {
      tf_static_frames_.insert(t.child_frame_id);
      frame_parent_[t.child_frame_id] = t.header.frame_id;
    }
  }

  std::string build_json() {
    bool have_grid, have_scan, have_pose_topic, have_odom_pose;
    uint32_t map_w = 0, map_h = 0;
    float map_res = 0.0f;
    double map_ox = 0.0, map_oy = 0.0, map_oyaw = 0.0;
    std::string map_frame;
    double map_ts = 0.0;
    std::vector<double> scan_pts;
    std::vector<double> odom_path;
    size_t path_len = 0;
    std::vector<double> pose_path;
    size_t pose_path_len = 0;
    double pose_x = 0.0, pose_y = 0.0, pose_yaw = 0.0;
    double scan_fps, odom_fps, map_fps, pose_fps;
    int loop_count = 0;
    double loop_last_ts = 0.0;
    {
      std::lock_guard<std::mutex> lock(data_mtx_);
      have_grid = have_grid_;
      if (have_grid) {
        map_w = grid_.info.width;
        map_h = grid_.info.height;
        map_res = grid_.info.resolution;
        map_ox = grid_.info.origin.position.x;
        map_oy = grid_.info.origin.position.y;
        const auto &q = grid_.info.origin.orientation;
        map_oyaw = std::atan2(2.0 * (q.w * q.z + q.x * q.y),
                              1.0 - 2.0 * (q.y * q.y + q.z * q.z));
        map_frame = grid_.header.frame_id;
        map_ts = grid_.info.map_load_time.sec + grid_.info.map_load_time.nanosec * 1e-9;
      }
      have_scan = have_scan_;
      scan_pts = scan_pts_;
      odom_path = odom_path_;
      path_len = odom_path.size() / 2;
      pose_path = pose_path_;
      pose_path_len = pose_path.size() / 2;
      have_pose_topic = have_pose_topic_;
      have_odom_pose = have_odom_pose_;
      // The odom pose projected through the map->odom transform is the live
      // corrected pose and updates at the odom rate (smooth). slam_toolbox's
      // /pose is the scan-matched pose (also correct) but published only once per
      // processed scan, so it is low-rate and "jumpy". Prefer odom for the marker;
      // fall back to /pose only when odom is unavailable.
      if (have_odom_pose) {
        pose_x = odom_pose_x_;
        pose_y = odom_pose_y_;
        pose_yaw = odom_pose_yaw_;
      } else if (have_pose_topic) {
        pose_x = pose_topic_x_;
        pose_y = pose_topic_y_;
        pose_yaw = pose_topic_yaw_;
      }
      scan_fps = scan_fps_.fps;
      odom_fps = odom_fps_.fps;
      map_fps = map_fps_.fps;
      pose_fps = pose_fps_.fps;
      loop_count = loop_count_;
      loop_last_ts = loop_last_ts_;
    }

    std::ostringstream ss;
    ss << "{";

    // Map metadata (the colorized PNG arrives on a separate WS frame).
    ss << "\"map\":{\"w\":" << map_w << ",\"h\":" << map_h << ",\"res\":" << map_res;
    ss << ",\"ox\":" << map_ox << ",\"oy\":" << map_oy << ",\"oyaw\":" << map_oyaw;
    ss << ",\"frame\":\"" << json_escape(map_frame) << "\"";
    ss << ",\"have\":" << (have_grid ? "true" : "false");
    ss << ",\"ts\":" << std::fixed << std::setprecision(3) << map_ts;
    ss.unsetf(std::ios::fixed);
    ss << std::setprecision(6);
    ss << "}";

    // Scan points in map frame (downsampled to ~360 for a bounded JSON).
    if (have_scan && !scan_pts.empty()) {
      ss << ",\"scan\":[";
      size_t n = scan_pts.size() / 2;
      size_t step = n / 360 + 1;
      bool first = true;
      for (size_t i = 0; i < n; i += step) {
        if (!first) ss << ",";
        first = false;
        ss << "[" << scan_pts[2 * i] << "," << scan_pts[2 * i + 1] << "]";
      }
      ss << "]";
    }
    ss << ",\"scan_have\":" << (have_scan ? "true" : "false");

    // Odom trajectory in map frame (downsampled to ~500).
    if (!odom_path.empty()) {
      ss << ",\"path\":[";
      size_t n = odom_path.size() / 2;
      size_t step = n / 500 + 1;
      bool first = true;
      for (size_t i = 0; i < n; i += step) {
        if (!first) ss << ",";
        first = false;
        ss << "[" << odom_path[2 * i] << "," << odom_path[2 * i + 1] << "]";
      }
      size_t last = n - 1;
      if (last % step != 0) {
        ss << ",[" << odom_path[2 * last] << "," << odom_path[2 * last + 1] << "]";
      }
      ss << "]";
    }
    ss << ",\"path_len\":" << path_len;

    // Slam /pose trajectory (scan-matched pose, already in map frame).
    if (!pose_path.empty()) {
      ss << ",\"pose_path\":[";
      size_t n = pose_path.size() / 2;
      size_t step = n / 500 + 1;
      bool first = true;
      for (size_t i = 0; i < n; i += step) {
        if (!first) ss << ",";
        first = false;
        ss << "[" << pose_path[2 * i] << "," << pose_path[2 * i + 1] << "]";
      }
      size_t last = n - 1;
      if (last % step != 0) {
        ss << ",[" << pose_path[2 * last] << "," << pose_path[2 * last + 1] << "]";
      }
      ss << "]";
    }
    ss << ",\"pose_path_len\":" << pose_path_len;

    // Current robot pose in map frame.
    if (have_pose_topic || have_odom_pose) {
      ss << ",\"pose\":{\"x\":" << pose_x << ",\"y\":" << pose_y << ",\"yaw\":" << pose_yaw
         << ",\"from\":\"" << (have_odom_pose ? "odom" : "pose") << "\"}";
    }

    // Topic FPS (wall-clock).
    ss << ",\"fps\":{\"scan\":" << scan_fps << ",\"odom\":" << odom_fps
       << ",\"map\":" << map_fps << ",\"pose\":" << pose_fps << "}";

    // Loop closure counter (from slam_toolbox/loop_closure_event). count is the
    // total number of accepted loop closures; last_ts is the sim-time stamp of
    // the most recent one, so the frontend can flash on a new event.
    ss << ",\"loop\":{\"count\":" << loop_count
       << ",\"last_ts\":" << std::fixed << std::setprecision(3) << loop_last_ts
       << "}";
    ss.unsetf(std::ios::fixed);
    ss << std::setprecision(6);

    // Resolved topic names, so the panel labels show the actual subscriptions.
    ss << ",\"topics\":{\"scan\":\"" << json_escape(scan_topic_)
       << "\",\"odom\":\"" << json_escape(odom_topic_)
       << "\",\"map\":\"" << json_escape(map_topic_)
       << "\",\"pose\":\"" << json_escape(pose_topic_) << "\"}";

    // TF frames (map/odom/base_link + static sensors). Each frame is emitted with
    // its pose in the map frame and its source (/tf vs /tf_static), so the
    // frontend can draw the transform tree and color labels by source topic.
    {
      std::set<std::string> tf_snapshot, tf_static_snapshot;
      std::map<std::string, std::string> parent_snapshot;
      {
        std::lock_guard<std::mutex> lock(data_mtx_);
        tf_snapshot = tf_frames_;
        tf_static_snapshot = tf_static_frames_;
        parent_snapshot = frame_parent_;
      }
      std::set<std::string> frames;
      frames.insert(tf_snapshot.begin(), tf_snapshot.end());
      frames.insert(tf_static_snapshot.begin(), tf_static_snapshot.end());
      for (const auto &kv : parent_snapshot) frames.insert(kv.second);
      frames.insert(map_frame_);

      ss << ",\"frames\":[";
      bool first = true;
      for (const auto &name : frames) {
        std::string src = "tf";
        if (name == map_frame_) {
          src = "root";
        } else if (tf_static_snapshot.count(name)) {
          src = "tf_static";
        }
        std::string parent;
        auto it = parent_snapshot.find(name);
        if (it != parent_snapshot.end()) parent = it->second;

        double px = 0, py = 0, pz = 0, qx = 0, qy = 0, qz = 0, qw = 1;
        if (name != map_frame_) {
          try {
            auto tf = tf_buffer_->lookupTransform(map_frame_, name, tf2::TimePointZero);
            px = tf.transform.translation.x;
            py = tf.transform.translation.y;
            pz = tf.transform.translation.z;
            qx = tf.transform.rotation.x;
            qy = tf.transform.rotation.y;
            qz = tf.transform.rotation.z;
            qw = tf.transform.rotation.w;
          } catch (const tf2::TransformException &) {
            continue;  // not (yet) connected to the map frame
          }
        }

        if (!first) ss << ",";
        first = false;
        ss << "{\"name\":\"" << json_escape(name) << "\""
           << ",\"x\":" << px << ",\"y\":" << py << ",\"z\":" << pz
           << ",\"qx\":" << qx << ",\"qy\":" << qy << ",\"qz\":" << qz << ",\"qw\":" << qw
           << ",\"src\":\"" << src << "\""
           << ",\"parent\":\"" << json_escape(parent) << "\"}";
      }
      ss << "]";
    }

    // The robot's base and odometry frame names, so the frontend can whitelist
    // the coordinate-axes display regardless of the robot's naming convention
    // (base_link vs base_footprint, odom vs odom_combined).
    ss << ",\"base_frame\":\"" << json_escape(base_frame_) << "\""
       << ",\"odom_frame\":\"" << json_escape(odom_frame_) << "\"";

    ss << "}";
    return ss.str();
  }

  // Params
  std::string scan_topic_, odom_topic_, map_topic_, pose_topic_, loop_closure_topic_;
  std::string map_frame_, odom_frame_, base_frame_;
  std::string host_;
  int port_;
  double publish_fps_;

  // tf2
  std::unique_ptr<tf2_ros::Buffer> tf_buffer_;
  std::unique_ptr<tf2_ros::TransformListener> tf_listener_;

  // Shared state + server
  std::shared_ptr<SharedVizState> viz_state_;
  std::shared_ptr<WebServer> server_;

  // Subscribers
  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_sub_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::Subscription<nav_msgs::msg::OccupancyGrid>::SharedPtr map_sub_;
  rclcpp::Subscription<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr pose_sub_;
  rclcpp::Subscription<tf2_msgs::msg::TFMessage>::SharedPtr tf_sub_;
  rclcpp::Subscription<tf2_msgs::msg::TFMessage>::SharedPtr tf_static_sub_;
  rclcpp::Subscription<slam_toolbox::msg::LoopClosureEvent>::SharedPtr loop_closure_sub_;

  // Latest data (written by callbacks, read by build_json).
  std::mutex data_mtx_;
  nav_msgs::msg::OccupancyGrid grid_;
  bool have_grid_ = false;
  std::vector<double> scan_pts_;
  bool have_scan_ = false;
  std::vector<double> odom_path_;
  double odom_pose_x_ = 0.0, odom_pose_y_ = 0.0, odom_pose_yaw_ = 0.0;
  bool have_odom_pose_ = false;
  bool have_odom_topic_ = false;  // true once /odom arrives; suppresses the TF fallback
  std::vector<double> pose_path_;
  double pose_topic_x_ = 0.0, pose_topic_y_ = 0.0, pose_topic_yaw_ = 0.0;
  bool have_pose_topic_ = false;
  // Frame names seen on /tf vs /tf_static, plus child->parent edges (for the
  // frontend to draw the transform tree and color labels by source topic).
  std::set<std::string> tf_frames_;
  std::set<std::string> tf_static_frames_;
  std::map<std::string, std::string> frame_parent_;
  // Loop closure tally (updated by loop_closure_callback).
  int loop_count_ = 0;
  double loop_last_ts_ = 0.0;

  // Timer for periodic JSON push
  rclcpp::TimerBase::SharedPtr timer_;

  // FPS tracking
  FpsTracker scan_fps_, odom_fps_, map_fps_, pose_fps_;
};

}  // namespace slam_toolbox_web

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::executors::MultiThreadedExecutor executor;
  auto node = std::make_shared<slam_toolbox_web::SlamToolboxWebNode>(rclcpp::NodeOptions());
  executor.add_node(node);
  executor.spin();
  rclcpp::shutdown();
  return 0;
}
