cmake_minimum_required(VERSION 3.15...3.31)
project(quant_kernel LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find the active interpreter and the pybind11 it ships with. Querying
# `python -m pybind11 --cmakedir` makes this work both under build isolation and
# with --no-build-isolation, on Windows (MSVC) and macOS (Clang) unchanged.
find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
if(NOT pybind11_DIR)
  execute_process(
    COMMAND "${Python_EXECUTABLE}" -m pybind11 --cmakedir
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE)
endif()
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(quant_kernel src/quant_kernel.cpp)

# Install to the wheel root so the module imports as `quant_kernel`.
install(TARGETS quant_kernel LIBRARY DESTINATION . RUNTIME DESTINATION .)
