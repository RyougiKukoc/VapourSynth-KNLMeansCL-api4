# KNLMeansCL
[![GitHub release](https://img.shields.io/github/release/Khanattila/KNLMeansCL.svg)](https://github.com/Khanattila/KNLMeansCL/releases) 

**KNLMeansCL** is an optimized OpenCL implementation of the Non-local means de-noising algorithm. The NLMeans filter, originally proposed by Buades et al., is a very popular filter for the removal of white Gaussian noise, due to its simplicity and excellent performance. The strength of this algorithm is to exploit the repetitive character of the image in order to de-noise the image unlike conventional de-noising algorithms, which typically operate in a local neighbourhood.

For end user **KNLMeansCL** is a plugin for **[AviSynth](http://avisynth.nl)**, **[AviSynth+](http://avs-plus.net/)** and for **[VapourSynth](http://www.vapoursynth.com)**. Windows, OS X and Linux are supported. Read more on the **[Wiki](https://github.com/Khanattila/KNLMeansCL/wiki)** and support on the **[Doom9](http://forum.doom9.org/showthread.php?t=171379)** forum.

**KNLMeansCL** is available under the **[GNU GPL v3 license](https://github.com/Khanattila/KNLMeansCL/blob/master/LICENSE)**.

## VapourSynth API4 Windows install

This fork can be installed as a VapourSynth API4 plugin package on Windows:

```powershell
pip install "vapoursynth-knlm @ git+https://github.com/RyougiKukoc/VapourSynth-KNLMeansCL-api4.git"
```

The VCS build first tries to reuse the tested release payload:

```text
https://github.com/RyougiKukoc/VapourSynth-KNLMeansCL-api4/releases/download/v1.1.1/knlmeanscl-msys2-ucrt64.zip
```

If the release asset is unavailable, the build hook falls back to a local
MSYS2/UCRT64 Meson build. Set `KNLMEANSCL_FORCE_BUILD=1` to force the local
build path, or `KNLMEANSCL_PREBUILT_URL=path-or-url-to-zip` to test a specific
prebuilt package.
