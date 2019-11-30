FROM python:buster
COPY . .
RUN apt-get update && \
    # uvloop
    apt-get install -y -qq libuv1-dev \
    # lxml
    libxml2-dev libxslt1-dev \
    # cairosvg
    libcairo2-dev \
    # Pillow
    libjpeg62-turbo-dev zlib1g-dev libfreetype6-dev liblcms2-dev libtiff5-dev tk8.6-dev tcl8.6-dev libwebp-dev libharfbuzz-dev libfribidi-dev libgif-dev \
    # wand
    imagemagick \
    # h5py
    libhdf5-dev \
    # debugging
    gdb \
    # apt is so noisy
    > /dev/null
    # always install numpy separately
RUN pip install -U git+https://github.com/numpy/numpy@master#egg=numpy --retries 30
    # install minor deps
RUN pip install -U "discord.py" "asyncpg" -q --retries 30
    # remove caches
RUN rm -rf /root/.cache/pip/* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    find /usr/local -depth \
        \( \
            \( -type d -a \( -name test -o -name tests \) \) \
            -o \
            \( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
        \) -exec rm -rf '{}' +

CMD ["python", "Referee.py"]