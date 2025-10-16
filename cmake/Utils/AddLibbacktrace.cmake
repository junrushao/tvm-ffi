include(ExternalProject)

function (_libbacktrace_compile)
  set(libbacktrace_source ${CMAKE_CURRENT_LIST_DIR}/../../3rdparty/libbacktrace)
  set(_build_dir ${CMAKE_CURRENT_BINARY_DIR}/libbacktrace/build)
  set(_prefix    ${CMAKE_CURRENT_BINARY_DIR}/libbacktrace)  # install dir

  file(MAKE_DIRECTORY ${_prefix})
  file(MAKE_DIRECTORY ${_build_dir})

  # Figure out target arch requested by the *CMake* build (authoritative).
  set(_archs "${CMAKE_OSX_ARCHITECTURES}")
  if(NOT _archs)
    set(_archs "${CMAKE_SYSTEM_PROCESSOR}")
  endif()
  list(GET _archs 0 _arch)
  string(TOLOWER "${_arch}" _arch_l)
  if(_arch_l MATCHES "aarch64|arm64|arm64e")
    set(_arch "arm64")
    set(_host_for_autoconf "aarch64-apple-darwin")
  elseif(_arch_l MATCHES "x86_64|amd64")
    set(_arch "x86_64")
    set(_host_for_autoconf "x86_64-apple-darwin")
  else()
    # Fallback; won’t happen on macOS wheels
    set(_host_for_autoconf "${_arch}-apple-darwin")
  endif()

  # Deployment target (scikit-build-core usually sets this to 11.0)
  set(_min "${CMAKE_OSX_DEPLOYMENT_TARGET}")
  if(NOT _min AND DEFINED ENV{MACOSX_DEPLOYMENT_TARGET})
    set(_min "$ENV{MACOSX_DEPLOYMENT_TARGET}")
  endif()

  # Arch + min-version flags for both compile & link
  set(_archflags "-arch ${_arch}")
  if(_min)
    set(_archflags "${_archflags} -mmacosx-version-min=${_min}")
  endif()

  # Hide symbols when using clang/appleclang/gnu
  set(symbol_hiding_flags "")
  if (CMAKE_C_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
    set(symbol_hiding_flags "-fvisibility=hidden -fvisibility-inlines-hidden")
  endif()

  # Use system clang; Rosetta default doesn’t matter once we force -arch
  if (CMAKE_SYSTEM_NAME MATCHES "Darwin" AND
      (CMAKE_C_COMPILER MATCHES "^/Library" OR CMAKE_C_COMPILER MATCHES "^/Applications"))
    set(_cc "/usr/bin/cc")
  else()
    set(_cc "${CMAKE_C_COMPILER}")
  endif()

  # Make stamps arch-specific to avoid reusing a prior x86_64 build
  set(_stamp_dir ${CMAKE_CURRENT_BINARY_DIR}/libbacktrace/stamps-${_arch})

  ExternalProject_Add(project_libbacktrace
    PREFIX              ${_prefix}
    SOURCE_DIR          ${libbacktrace_source}
    BINARY_DIR          ${_build_dir}
    STAMP_DIR           ${_stamp_dir}
    LOG_DIR             ${_prefix}/logs-${_arch}

    # Set environment so configure uses the right arch regardless of Rosetta
    CONFIGURE_COMMAND
      ${CMAKE_COMMAND} -E env
        CC=${_cc}
        CPP=${_cc}\ -E
        AR=${CMAKE_AR}
        RANLIB=${CMAKE_RANLIB}
        NM=${CMAKE_NM}
        STRIP=${CMAKE_STRIP}
        CFLAGS=${_archflags}\ ${CMAKE_C_FLAGS}\ ${symbol_hiding_flags}
        LDFLAGS=${_archflags}\ ${CMAKE_EXE_LINKER_FLAGS}
      ${libbacktrace_source}/configure
        --prefix=${_prefix}
        --with-pic
        --host=${_host_for_autoconf}

    BUILD_COMMAND       $(MAKE) -j
    INSTALL_DIR         ${_prefix}
    INSTALL_COMMAND     $(MAKE) install

    BUILD_BYPRODUCTS
      "${_prefix}/lib/libbacktrace.a"
      "${_prefix}/include/backtrace.h"

    LOG_CONFIGURE ON
    LOG_BUILD     ON
    LOG_INSTALL   ON
    LOG_MERGED_STDOUTERR ON
    LOG_OUTPUT_ON_FAILURE ON
  )

  add_library(libbacktrace STATIC IMPORTED)
  add_dependencies(libbacktrace project_libbacktrace)
  set_target_properties(libbacktrace PROPERTIES
    IMPORTED_LOCATION             ${_prefix}/lib/libbacktrace.a
    INTERFACE_INCLUDE_DIRECTORIES ${libbacktrace_source}
  )
endfunction()

if (NOT MSVC)
  _libbacktrace_compile()
endif()
