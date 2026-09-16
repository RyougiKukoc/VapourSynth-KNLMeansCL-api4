# KNLMeansCL
[![GitHub release](https://img.shields.io/github/release/Khanattila/KNLMeansCL.svg)](https://github.com/Khanattila/KNLMeansCL/releases) 

**KNLMeansCL** is an optimized OpenCL implementation of the Non-local means de-noising algorithm. The NLMeans filter, originally proposed by Buades et al., is a very popular filter for the removal of white Gaussian noise, due to its simplicity and excellent performance. The strength of this algorithm is to exploit the repetitive character of the image in order to de-noise the image unlike conventional de-noising algorithms, which typically operate in a local neighbourhood.

For end user **KNLMeansCL** is a plugin for **[AviSynth](http://avisynth.nl)**, **[AviSynth+](http://avs-plus.net/)** and for **[VapourSynth](http://www.vapoursynth.com)**. Windows, OS X and Linux are supported. Read more on the **[Wiki](https://github.com/Khanattila/KNLMeansCL/wiki)** and support on the **[Doom9](http://forum.doom9.org/showthread.php?t=171379)** forum.

**KNLMeansCL** is available under the **[GNU GPL v3 license](https://github.com/Khanattila/KNLMeansCL/blob/master/LICENSE)**.

## VapourSynth API4 install

This fork can be installed as a VapourSynth API4 plugin package on Windows or
Linux x86_64:

```powershell
pip install "vapoursynth-knlm @ git+https://github.com/RyougiKukoc/VapourSynth-KNLMeansCL-api4.git"
```

The VCS build first tries to reuse the tested platform Release payload:

```text
https://github.com/RyougiKukoc/VapourSynth-KNLMeansCL-api4/releases/download/v1.1.2/knlmeanscl-msys2-ucrt64.zip
https://github.com/RyougiKukoc/VapourSynth-KNLMeansCL-api4/releases/download/v1.1.2/knlmeanscl-linux-x86_64.zip
```

If the matching Release asset is unavailable, the build hook runs a native
Meson build. Linux source builds discover the installed VapourSynth wheel's
API4 headers and pkg-config metadata; macOS has no prebuilt asset and therefore
uses the same native fallback. Set `KNLMEANSCL_FORCE_BUILD=1` to force a local
build, or `KNLMEANSCL_PREBUILT_URL=path-or-url-to-zip` to test a specific
payload.

KNLMeansCL requires a working vendor OpenCL ICD to render frames. The Linux
payload includes the OpenCL loader, but an NVIDIA, AMD, Intel, or other device
ICD remains a host driver requirement.
