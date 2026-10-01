

​	D1-朗毅控制演示


## 方式一：从源码构建

```bash
git clone <repo-url>
cd D1_langyi_sdk_demo
colcon build
```

构建完成后启动：

```bash
bash start_D1.sh
```

## 方式二：deb 包安装

从仓库根目录下载 `d1-langyi-sdk_1.0.0_arm64.deb`，然后在机器人上执行：

```bash
sudo dpkg -i d1-langyi-sdk_1.0.0_arm64.deb
```

安装完成后服务可手动启动，项目文件部署至 `/opt/d1_langyi_sdk_demo/`。

查看服务状态：

```bash
systemctl status d1_langyi.service
```

卸载：

```bash
sudo dpkg -r d1-langyi-sdk
```

如需自行打包 deb：

```bash
bash build_deb.sh
```


