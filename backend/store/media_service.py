"""One image validation and normalization path for the web manager and Android."""
from io import BytesIO
from uuid import uuid4
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES=2*1024*1024
IMAGE_FORMATS={"image/jpeg":"JPEG","image/png":"PNG","image/webp":"WEBP"}

class ImageUploadError(ValueError):
    def __init__(self,message,status=400):
        super().__init__(message)
        self.status=status

def store_product_image(raw,mime):
    if len(raw)>MAX_IMAGE_BYTES:
        raise ImageUploadError("حجم تصویر حداکثر ۲ مگابایت است.",413)
    if mime not in IMAGE_FORMATS:
        raise ImageUploadError("فرمت تصویر معتبر نیست.")
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format!=IMAGE_FORMATS[mime] or source.width*source.height>16_000_000:
                raise ImageUploadError("فرمت یا ابعاد تصویر معتبر نیست.")
            image=ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1600,1600))
            output=BytesIO()
            image.save(output,"JPEG",quality=86)
    except ImageUploadError:
        raise
    except (ValueError,UnidentifiedImageError,OSError,Image.DecompressionBombError):
        raise ImageUploadError("محتوای تصویر معتبر نیست.") from None
    return default_storage.save(f"products/{uuid4().hex}.jpg",ContentFile(output.getvalue()))
