project('KNLMeansCL',
        'cpp',
        default_options : ['cpp_std=c++11', 'buildtype=release'],
        license : 'GPL-3',
        version : '1.1.2')

add_project_arguments('-DCL_TARGET_OPENCL_VERSION=120', language : 'cpp')

vapoursynth = dependency('vapoursynth')
install_dir = join_paths(vapoursynth.get_pkgconfig_variable('libdir'), 'vapoursynth')
deps = [vapoursynth]

opencl_dep = dependency('OpenCL', required : false)
if not opencl_dep.found()
    opencl_dep = meson.get_compiler('cpp').find_library('OpenCL')
endif
boost_dep = dependency('boost', modules : ['filesystem', 'system'])
deps += [opencl_dep, boost_dep]

link_args = []
if host_machine.system() == 'linux'
    # Linux release zips carry their non-system runtime libraries beside the
    # plugin, so the loader must resolve them from the plugin directory.
    link_args += ['-Wl,-rpath,$ORIGIN']
endif

src = [
    'KNLMeansCL/NLMAvisynth.h',
    'KNLMeansCL/NLMAvisynth.cpp',
    'KNLMeansCL/NLMDefault.h',
    'KNLMeansCL/NLMKernel.cpp',
    'KNLMeansCL/NLMKernel.h',
    'KNLMeansCL/NLMVapoursynth.cpp',
    'KNLMeansCL/NLMVapoursynth.h',
    'KNLMeansCL/shared/common.cpp',
    'KNLMeansCL/shared/common.h',
    'KNLMeansCL/shared/ocl_utils.cpp',
    'KNLMeansCL/shared/ocl_utils.h',
    'KNLMeansCL/shared/startchar.cpp',
    'KNLMeansCL/shared/startchar.h']

library(
    'knlmeanscl',
    src,
    dependencies : deps,
    link_args : link_args,
    include_directories : include_directories('KNLMeansCL/avisynth'),
    install_dir : install_dir,
    install : true)
