# Monitoring System (MSys)

## Installation

### Dependencies

1. A C++20 compatible compiler, e.g., GCC 12.1.0 or later
([Steps](#c-20-compatible-compiler-installation)).
2. ProtocolBuffer compiler and runtime library, currently using version 30.2
([Steps](#protobuf-installation)).

#### Before Started

Using virtual environment for python is a good practice. In this doc, all setup code example use
`conda` as the example environment manager.

What should be done in the virtual environment:

- Install python-specific modules
- Configuring & compiling the monitoring_sys module
- Run any python code that uses the monitoring_sys module

What should **NOT** be done in virtual environment

- Build required libraries (e.g., protobuf) in virtual environment for a user-wide or system-wide
installation!

This is because that the host python and conda python might be different in python version,
installed lib, etc.

#### C++ 20 Compatible Compiler Installation

Check if system compiler already have the capability, if so, this step can be skipped.

To install a C++ 20 compatible compiler in the virtual environment, for example, `gcc=12.1.0`, run

```bash
conda install -c conda-forge gcc=12.1.0
```

#### Protobuf Installation

Install protobuf compiler and runtime library (modified from
[PROTOBUF_CMAKE](https://github.com/protocolbuffers/protobuf/blob/main/cmake/README.md)).
Currently, we are using version `v30.2`.

```bash
# Clone the protobuf repository
git clone https://github.com/protocolbuffers/protobuf.git
cd protobuf
git submodule update --init --recursive
git checkout v30.2
# Make & Install to  ~/.local
mkdir build && cd build
cmake .. -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
         -DBUILD_SHARED_LIBS=ON \
         -Dprotobuf_BUILD_SHARED_LIBS=ON \
         -Dprotobuf_BUILD_TESTS=OFF \
         -DCMAKE_CXX_STANDARD=17 \
         -DCMAKE_BUILD_TYPE=Release \
         -DCMAKE_INSTALL_PREFIX="$HOME/.local"
cmake --build . --config Release -j
make install -j
```

### Building MSys

If you decide to run the application in a python virtual environment, perform the following steps in
the virtual environment.

#### Preparation

Execute the following instructions to install all the dependencies for the project.

```bash
# install pip-compile for python package dependency resolution
python3 -m pip install pip-tools

# configure MSys and generate a list of all required python packages
mkdir build && cd build
cmake ..
make generate_py3_requirements
python3 -m pip install -r ../requirements.txt
```

#### Build MSys Shared Library and Position the Output Product to `src/monitoring_sys`

Run the following commands in the project's build folder.

```bash
cmake -DCMAKE_BUILD_TYPE=Release ..
make libmsys_pymod -j
```

### Examples of Running MSys with Existing Code

There are examples of how MSys can be properly configured and used with existing code in
`<proj_root>/example/monitoring_sys`

1. `test_run.py`
    - Try to configure a MSys with yaml file and test run it without load.
    - Output will be saved to `<proj_root>/example/monitoring_sys/output/<program_invoke_timestamp>`
    - Output folder contains
        - Translated MSys config (user need to export this manually)
        - `libmsys.log`, log file outputted by the libmsys submodule
        - Possible `python_rt.log` if any error encountered in the python runtime
        - Several `<monitor_name>.pb.bin`, the serial format for the protobuf that records all the
          statistics
        - **(TBA)** A file contains the metadata for each of the serialized outputs for later
          identifying and parsing of these serialized outputs
2. `test_parser.py`
    - After running the MSys, attempt to create plots according to the data saved during the
    recording phase.
    - It will parse all the `<monitor_name>.pb.bin`
    > **TODO:** Currently only CPUMetrics and GPUMetrics have parser, and their field name is
    > hard-coded, enhance the functionality with the metadata file in the future

The organization format for each protobuf is specified as follows

- A file might contains multiple protobuf serialized messages
- Each message have the following format (no padding between fields)
  - An integer (64 bit) specifying the length for the current message (4B)
  - A serialized protobuf message by the format `<monitor_name>MetricsTimeSeries` (Length Specified
    by the previous field)
- The message splitting policy is based on serialized protobuf size, so one message may contain
  statistics for multiple time points, refer to the `resource/proto/<monitor_name>_metrics.proto`
  for more information
- Different parse format may be required for different monitor types

### Potential Problems

#### GCC version is too Low in Conda Environment

##### Corresponding Error

- ImportError: <CONDA_ENV>/lib/libstdc++.so.6: version `GLIBCXX_3.4.30' not found (required by
  <INSTALL_PATH>/lib/libabsl_synchronization.so.2501.0.0)

##### Solution

The c++ compiler used is below minimum requirement, update c++ compiler.

<!-- ## Components

### MSys

A collection of meters. TBD

### Meter

#### CPUMeter

TBD

#### MemMeter

TBD

#### GPUMeter

TBD

#### DiskMeter

TBD

#### ProcMeter

TBD -->

### Usage Examples

#### Running

`python3 example/monitoring_sys_lib/test_run.py`

#### Stat Parsing

`python3 example/monitoring_sys_lib/test_parser.py`
