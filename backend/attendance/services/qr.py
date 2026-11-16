"""QR code image generation (server side)."""
import base64
import io


def qr_png_data_uri(text: str) -> str:
    """Render ``text`` as a QR code and return it as a ``data:`` URI (PNG)."""
    import qrcode  # imported lazily so that the pure-logic modules need no extra packages
    from qrcode.constants import ERROR_CORRECT_M

    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
