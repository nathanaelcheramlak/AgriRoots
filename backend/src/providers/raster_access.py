"""GDAL reads through a Python seekable opener; every remote range uses SafeHttp."""

import asyncio
import io
import re
from urllib.parse import urlsplit

from src.integrations.contracts import ConnectorError
from src.providers.agriculture import numeric, require


class RemoteRaster(io.RawIOBase):
    block_size = 65536

    def __init__(self, http, url, loop):
        self.http, self.url, self.loop = http, url, loop
        self.position = 0
        self.blocks = {}
        self.length = None

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def block(self, index):
        if index not in self.blocks:
            require(len(self.blocks) < 128, "Raster exceeds the 8 MB range-read budget")
            start = index * self.block_size
            response = asyncio.run_coroutine_threadsafe(
                self.http.raw(
                    "GET",
                    self.url,
                    headers={"Range": f"bytes={start}-{start + self.block_size - 1}", "Accept": "image/tiff"},
                ),
                self.loop,
            ).result()
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("content-range", ""))
            require(response.status_code == 206 and match is not None, "Raster server must support byte ranges")
            first, last, total = map(int, match.groups())
            require(
                first == start
                and last < total
                and 0 < total <= 128 * 1024**3
                and last - first + 1 == len(response.content) <= self.block_size,
                "Invalid raster byte range",
            )
            require(self.length in (None, total), "Raster changed during extraction")
            self.length = total
            self.blocks[index] = response.content
        return self.blocks[index]

    def seek(self, offset, whence=0):
        if whence == 2 and self.length is None:
            self.block(0)
        target = offset + (self.position if whence == 1 else self.length if whence == 2 else 0)
        require(target >= 0 and whence in (0, 1, 2), "Invalid raster seek")
        self.position = target
        return target

    def read(self, size=-1):
        if self.length is None:
            self.block(0)
        size = self.length - self.position if size < 0 else min(size, self.length - self.position)
        require(size <= 8 * 1024**2, "Unbounded raster read rejected")
        parts = []
        while size > 0:
            block = self.block(self.position // self.block_size)
            offset = self.position % self.block_size
            part = block[offset : offset + size]
            require(bool(part), "Truncated raster range")
            parts.append(part)
            self.position += len(part)
            size -= len(part)
        return b"".join(parts)

    def readinto(self, buffer):
        value = self.read(len(buffer))
        buffer[: len(value)] = value
        return len(value)


async def raster_pixel(http, url, longitude, latitude, *, full=False):
    try:
        import rasterio
        from rasterio.io import MemoryFile
    except ImportError:
        raise ConnectorError("UNSUPPORTED_CAPABILITY", "Install the backend raster dependency group") from None

    def sample(dataset):
        require(
            dataset.crs and dataset.crs.to_epsg() == 4326 and dataset.count == 1, "Unexpected raster CRS or band count"
        )
        require(
            dataset.bounds.left <= longitude < dataset.bounds.right
            and dataset.bounds.bottom < latitude <= dataset.bounds.top,
            "Requested point outside raster coverage",
        )
        pixel = next(dataset.sample([(longitude, latitude)], masked=True))
        if bool(pixel.mask[0]):
            return None
        value = float(pixel[0])
        require(numeric(value), "Non-finite raster pixel")
        return {"raw_value": value, "resolution_degrees": list(dataset.res), "crs": "EPSG:4326"}

    if full:
        response = await http.raw("GET", url, headers={"Accept": "image/tiff"})
        require(response.content[:4] in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"), "Expected TIFF bytes")

        def local():
            with rasterio.Env(GDAL_PAM_ENABLED="NO"), MemoryFile(response.content) as memory, memory.open() as dataset:
                return sample(dataset)

        result = await asyncio.to_thread(local)
        return result

    loop = asyncio.get_running_loop()

    def ranged():
        # Rasterio's custom opener uses our file object rather than /vsicurl.
        # A single threaded read keeps all network accounting on the main event loop.
        opened = []

        def opener(path, mode="rb"):
            if path != "provider.tif":
                raise FileNotFoundError(path)
            stream = RemoteRaster(http, url, loop)
            opened.append(stream)
            return stream

        try:
            with (
                rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_PAM_ENABLED="NO"),
                rasterio.open("provider.tif", opener=opener) as dataset,
            ):
                return sample(dataset)
        finally:
            for stream in opened:
                stream.close()

    return await asyncio.to_thread(ranged)


def wapor_object(raster):
    uri = raster.get("gsutilUri", "")
    url = (
        "https://storage.googleapis.com/" + uri[5:]
        if uri.startswith("gs://fao-gismgr-")
        else raster.get("downloadUrl", "")
    )
    p = urlsplit(url)
    require(
        p.scheme == "https"
        and p.netloc == "storage.googleapis.com"
        and p.path.startswith("/fao-gismgr-")
        and p.path.endswith(".tif")
        and not p.query
        and not p.fragment,
        "Unexpected WaPOR raster object",
    )
    return url
