"""ShipToast message formatting."""


import re


url_pattern = re.compile(
    "((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?\+-=\\\.&](#!)?)*)"
)


def _youtube_embed(youtube_link):
    """Returns an iframe to embed the youtube link in."""

    return (
        '<iframe title="Embedded YouTube" width="480" height="390" '
        'src="https://www.youtube.com/embed/{}" frameborder="0" '
        'allowfullscreen></iframe>'
    ).format(youtube_link)


def format_message(message):
    """Adds <a> tags to links, turn image links into <img> tags."""

    image_endings = ("jpeg", "JPEG", "jpg", "JPG", "gif", "GIF", "png", "PNG")
    formatted = []
    last_match = 0
    for match in re.finditer(url_pattern, message):
        span = match.span()
        formatted.append(message[last_match:span[0]])
        link = message[span[0]:span[1]]
        link_extension = link.split(".")[-1]
        if "youtube.com/watch?v=" in link:
            formatted.append(_youtube_embed(
                link.split("youtube.com/watch?v=")[-1].split("&")[0]
            ))
        elif "youtu.be/" in link:
            formatted.append(_youtube_embed(
                link.split("youtu.be/")[-1].split("?")[0]
            ))
        elif link_extension in image_endings:
            formatted.append(
                '<a href="{}"><img src="{}" /></a>'.format(link, link)
            )
        else:
            formatted.append('<a href="{}">{}</a>'.format(link, link))

        last_match = span[1]

    formatted.append(message[last_match:])
    return "".join(formatted)
