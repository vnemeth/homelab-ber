FROM alpine:3.22
RUN apk add --no-cache rtl-sdr ffmpeg python3
COPY fmradio.py /fmradio.py
CMD ["python3", "-u", "/fmradio.py"]
