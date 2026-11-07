# Debian, as it packages welle-cli (in welle.io, which also brings the Qt GUI's
# libraries: most of the image's 680 MB). lame encodes FM to MP3
FROM debian:trixie-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends rtl-sdr welle.io lame python3 \
 && rm -rf /var/lib/apt/lists/*
COPY fmradio.py /fmradio.py
CMD ["python3", "-u", "/fmradio.py"]
