# common monitoring_sys variables
# it sets the following variables for connivent target generation
# [MSYS_SOURCES]:   all source files of the monitoring_sys
# [MSYS_LIBRARIES]: all libraries needed by the monitoring_sys
# [MSYS_INCLUDES]:  all required include directories for the monitoring_sys
# [PROTO_PY_SOURCES]: generated protobuf python interfaces

find_package(CUDAToolkit REQUIRED 12.4)
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

# protobuf compilation
file(GLOB PROTO_SOURCES ${RESOURCE_DIR}/proto/*.proto)
proto_compile(MSYS_PROTO_DEP
    SOURCE_DIR   ${RESOURCE_DIR}/proto
    CXX_DEST_DIR ${CMAKE_CURRENT_LIST_DIR}/generated/proto
    PY_DEST_DIR  ${PYTHON_SRC_DIR}/proto
    GEN_SOURCES  PROTO_SOURCES
    SOURCES      ${PROTO_SOURCES}
)

# get generated cxx source files
set(PROTO_CC_SOURCES ${PROTO_SOURCES})
list(FILTER PROTO_CC_SOURCES INCLUDE REGEX "\\.cc$")
# get generated python source files
set(PROTO_PY_SOURCES ${PROTO_SOURCES})
list(FILTER PROTO_PY_SOURCES INCLUDE REGEX "\\.py$")

# === determine [MSYS_SOURCES] ===
set(MSYS_SOURCES "")
# find all build sources
file(GLOB MSYS_CC_SOURCES ${CMAKE_CURRENT_LIST_DIR}/src/*.cc)
# aggregate them
list(APPEND MSYS_SOURCES ${PROTO_CC_SOURCES})
list(APPEND MSYS_SOURCES ${DATELIB_SOURCES})
list(APPEND MSYS_SOURCES ${MSYS_CC_SOURCES})

# === determine [MSYS_DEPENDS] ===
# find all dependencies
set(MSYS_DEPENDS
    # CUDA libraries
    CUDA::cupti
    CUDA::nvml
    # protobuf and absl libraries
    protobuf::libprotobuf
    absl::log
    # for zoned date support
    date::date-tz)

# === MSYS_INCLUDES [MSYS_INCLUDES] ===
# find all includes
set(MSYS_INCLUDES
    # project
    ${CMAKE_CURRENT_LIST_DIR}
    # third party
    ${PYBIND11_INCLUDES}
    ${DATELIB_INCLUDES}
    # external libraries
    ${CUDAToolkit_INCLUDE_DIRS}
    ${Python3_INCLUDE_DIRS}
    ${Protobuf_INCLUDE_DIRS})
