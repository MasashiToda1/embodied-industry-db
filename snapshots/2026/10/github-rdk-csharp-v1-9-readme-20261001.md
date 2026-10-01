# Flexiv RDK CSharp

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0.html)

**Flexiv RDK CSharp** provides C# developers with an easy way to work with [**Flexiv RDK**](https://github.com/flexivrobotics/flexiv_rdk). It uses [**P/Invoke**](https://learn.microsoft.com/en-us/dotnet/standard/native-interop/pinvoke) to call most of the functions from the RDK C++ interface, excluding *flexiv::rdk::Model* and *flexiv::rdk::Scheduler*.

## Reference

For detailed usage instructions and API documentation, refer to the [Flexiv RDK Home Page](https://www.flexiv.com/software/rdk).

## Compatibility

| **Language** | **Supported OS** | **Platform** | **Compiler / Runtime** | **Notes**                        |
| ------------ | ---------------- | ------------ | ---------------------- | -------------------------------- |
| **C++**      | Windows 10+      | x64          | MSVC v14.2+ (VS 2019+) | Builds dynamic library (`.dll`)  |
| **C#**       | Windows 10+      | x64          | .NET 5.0 or later      | Uses `DllImport` to call C++ DLL |

## Project Structure

It calls the C++ interfaces from [flexiv_rdk](https://github.com/flexivrobotics/flexiv_rdk) via P/Invoke and wraps them with C# interfaces.

- **csharp/**: C# project containing the wrapper and usage examples.
  - **FlexivRdk/**: C# wrapper classes calling functions from the native DLL.
  - **Examples/**: Example programs demonstrating usage of the C# wrappers.
  - `Program.cs`: Entry point, runs selected example programs.
- **cpp_wrapper/**: C++ project wrapping **flexiv_rdk** C++ interfaces and generating a dynamic library (`.dll`).
- **install/**: Installs flexiv_rdk dependencies and C++ wrapper dynamic libraries to custom output directories.
- **released_dll/**: Precompiled dynamic libraries for immediate use.
- **third_party/**：Third-party library folder.

## Usage

This repository provides C# bindings for the Flexiv RDK. You can either directly use the existing interfaces, or extend the native C++ wrapper and rebuild the dynamic libraries as needed.

### Option:1 Direct Use (Run Existing Examples)

If you simply want to run the C# examples using the provided native DLLs, follow these steps:

1. Navigate to the C# project directory:

        cd flexiv_rdk_csharp/csharp

2. Build the project in Release mode:

        dotnet build csharp.csproj -c Release

   NOTE: During the build process, DLLs from the released_dll directory will be automatically copied to the output directory.

3. Run the example program:

        dotnet run --project csharp.csproj -c Release

   NOTE: Usage instructions will appear in the command line. Please select a sample program, such as:

        dotnet run --project csharp.csproj basics1_display_robot_states Rizon4-123456

4. If you want to use the interface in your own project:
    - Include the .cs files from the **csharp/FlexivRdk/** folder.
    - Place the dynamic libraries from **released_dll/** in the same directory as your compiled .exe file.

### Option 2: Extend C++ Interface and Rebuild DLL

If you want to modify or extend the native C++ wrapper (cpp_wrapper), or rebuild the DLLs from source with latest dependencies:

1. Navigate to the project root directory:

        cd flexiv_rdk_csharp

2. Run the build script:

        bash build_and_install_flexiv_rdk_dll.sh

   NOTE: On Windows, if the project involves long file paths, please ensure that Long Path Support is enabled in the system settings to avoid build or runtime errors caused by path length limitations.

    - Download and install flexiv_rdk and third-party dependencies.
    - Build the C++ wrapper.
    - Generate and install updated DLLs to **install/** directory

   NOTE: After rebuilding, make sure to copy the new DLLs from **install/cpp_wrapper/bin/** into your C# app's output directory (same place as the .exe).

## License

This project is licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
