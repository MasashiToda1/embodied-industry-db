# rules_layer_optimizer

This Bazel ruleset provides building blocks for creating optimized application
OCI images based on an executable entrypoint, e.g. a `py_binary` target.

The following are provided:

- Build separate image layers for each apt or python package, shared across all
  consuming applications
- Sort layers by size
- Flatten the long-tail of small packages, to stay under a configurable layer
  cap or size threshold
- Infer apt package dependencies and environment variables
- Examples for how to combine all of the above into a simple `py_image` macro,
  for producing an OCI-compatible image from a `py_binary`

## Building blocks

| Entrypoint | Symbols | Purpose |
| --- | --- | --- |
| `//layers:defs.bzl` | `layer_group`, `optimized_layers_plan`, `MAX_DOCKER_LAYERS` | Group tar inputs and plan which layers to keep separate or combine |
| `//layers:providers.bzl` | `LayerTarsInfo`, `SizeHintInfo` | Expose ordered layer archives and size estimates to the optimizer |
| `//layers:distroless.bzl` | `optimized_layers` | Create optimized layer archives using rules_distroless |
| `//inference:defs.bzl` | `layer_inference`, `layer_inference_bundle`, `inferred_layers`, `env_inference`, `env_inference_bundle`, `env_file` | Select layers and environment variables from dependency labels |
| `//inference:extensions.bzl` | `oci_image_inference` | Configure dependency traversal and package-size estimates |
| `//apt:defs.bzl` | `apt_inference`, `inferred_apt_deps` | Select APT package layers from application dependencies |
| `//python:aspect_rules_py.bzl` | `py_image_layer`, `pip_layer_reducer` | Split aspect_rules_py binaries into reusable package and source layers |
| `//python:rules_python.bzl` | `py_image_layer`, `pip_layer_reducer` | Split rules_python binaries into interpreter, package, and source layers |
| `//python:inference.bzl` | `layer_inference`, `inferred_layers`, `apt_inference`, `inferred_apt_deps`, `env_inference`, `env_file` | Select layers, APT packages, and environment variables from Python dependencies |

## How to use it

Add the dependency to your `MODULE.bazel`:

```starlark
bazel_dep(name = "rules_layer_optimizer", version = "0.1.0")
```

Then, there are 3 basic steps. Each stage is modular, so hand-rolled
replacements work fine too.

### 1. Produce layer candidates with size hints

This is the step with the most variability, as it depends on which dependencies
your repo uses (`rules_oci` | `rules_img`, and `rules_python` |
`aspect_rules_py`). Regardless of your choices, the goal remains the same:
produce candidate image layers that are efficient and also accompanied by size
hints via the `SizeHintInfo` provider:

```starlark
load("@rules_layer_optimizer//python:aspect_rules_py.bzl", "py_image_layer")

py_image_layer(
    name = "app_layers",
    binary = ":app",
    interpreter_tar = ":interpreter",
    python_toolchain = "@python_interpreters//:current_py_toolchain",
    strip_prefix = "my/package/app",
)
```

With `rules_python`, load `python:rules_python.bzl` and omit `interpreter_tar`
and `python_toolchain`. Either adapter emits `:app_layers_pip` with
`LayerTarsInfo` and `SizeHintInfo`, plus unsized interpreter and source tars. A
hand-rolled rule should return the same providers:

```starlark
return [
    DefaultInfo(files = depset([tar])),
    LayerTarsInfo(tars = [tar]),
    SizeHintInfo(sizes = {tar: size_bytes}),
]
```

### 2. Optimize the layers

From the layer candidates, group and optimize them with `optimized_layers`. Note
that `SizeHintInfo` is not required on all candidates, the rule will use the
hints when available but they only matter for groups where in-group reordering
and flattening is desired:

```starlark
load("@rules_layer_optimizer//layers:defs.bzl", "layer_group")
load("@rules_layer_optimizer//layers:distroless.bzl", "optimized_layers")

optimized_layers(
    name = "layers",
    groups = [layer_group(
        name = "packages",
        targets = [":package_a", ":package_b"],
        overflow = "flatten",
    )],
    layer_budget = 10,
    size_bytes_threshold = 1024 * 1024,
    visibility = ["//visibility:public"],
)
```

### 3. Build the image

The output of `optimized_layers` can be fed directly into `oci_image` or
`image_manifest`:

```starlark
load("@rules_oci//oci:defs.bzl", "oci_image")

oci_image(
    name = "image",
    base = "@ubuntu",
    entrypoint = ["/app"],
    env = ":env",
    tars = [":layers"],
)
```

`rules_img` takes the same archives as `layers` and the environment file as `env_file`:

```starlark
load("@rules_img//img:image.bzl", "image_manifest")
load("@rules_img_images.bzl", "image")

image_manifest(
    name = "image",
    base = image("ubuntu"),
    entrypoint = ["/app"],
    env_file = ":env",
    layers = [":layers"],
)
```

## Try it locally

The [examples](examples/README.md) are two modules that wrap these pieces in a
macro taking only `name` and a `py_binary`: one with rules_oci and
aspect_rules_py, and one with rules_img and rules_python.

```sh
bazel test //...
(cd examples/py_image_with_rules_oci_and_aspect_rules_py && bazel test //...)
(cd examples/py_image_with_rules_img_and_rules_python && bazel test //...)
```

Start with [configuration](docs/configuration.md) and the capability docs:
[layers](layers/README.md), [inference](inference/README.md),
[Python](python/README.md), and [APT](apt/README.md).
See [compatibility](docs/compatibility.md) for supported dependency minimums and
[CONTRIBUTING.md](CONTRIBUTING.md) for development checks.

## Future work

The optimizations provided by this ruleset are not useful only for Python. The
same strategy can be applied to any other language whose third-party packages
remain intact in the final runtime tree. A shared package directory, such as a
Java archive, a `node_modules` tree, or a Ruby gem, can be its own reusable
image layer. C++ and Rust are unsuitable: compilation folds dependencies into
the binary, so no package boundary remains to share across images.
