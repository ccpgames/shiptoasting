"""ShipToast message formatting."""


import re


url_pattern = re.compile(
    "((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?\+-=\\\.&](#!)?)*)"
)
gfycat_pattern = re.compile("(https?)://gfycat.com/[^/]*")


def _youtube_embed(youtube_link):
    """Returns an iframe to embed the youtube link in."""

    return (
        '<iframe title="Embedded YouTube" width="480" height="390" '
        'src="https://www.youtube.com/embed/{}" frameborder="0" '
        'allowfullscreen></iframe>'
    ).format(youtube_link)


def _gifv_embed(gifv_link):
    """Returns a video link to imgur for the gifv."""

    return (
        '<video poster="https://i.imgur.com/{id}h.jpg" preload="auto" '
        'autoplay="autoplay" muted="muted" loop="loop" '
        'width="500" height="300">'
        '<source src="https://i.imgur.com/{id}.mp4" type="video/mp4">'
        '<object type="application/x-shockwave-flash" height="300" width="500"'
        ' data="https://s.imgur.com/include/flash/gifplayer.swf?imgur_video='
        'https://i.imgur.com/{id}.mp4&imgur_width=500&imgur_height=300">'
        '<param name="movie" value="https://s.imgur.com/include/flash/'
        'gifplayer.swf?imgur_video=https://i.imgur.com/{id}.mp4&'
        'imgur_width=500&imgur_height=300" />'
        '<param name="allowscriptaccess" value="never" />'
        '<param name="flashvars" value="height=300&amp;width=500" />'
        '<param name="width" value="500" />'
        '<param name="height" value="300" />'
        '<param name="version" value="0" />'
        '<param name="scale" value="scale" />'
        '<param name="salign" value="tl" />'
        '<param name="wmode" value="opaque" />'
        '</object>'
        '</video>'
    ).format(
        id=gifv_link.split(".")[-2].split("/")[-1]
    )


def _gfycat_embed(gfycat_link):
    return (
        '<video poster="https://thumbs.gfycat.com/{id}-poster.jpg" autoplay '
        'muted loop width="500" height="300">'
        '<source src="https://giant.gfycat.com/{id}.mp4" type="video/mp4">'
        '</video>'
    ).format(
        id=gfycat_link.split("/")[-1]
    )


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
        gfycat_match = re.match(gfycat_pattern, link)
        if gfycat_match:
            formatted.append(_gfycat_embed(link[:gfycat_match.end()]))
        elif "youtube.com/watch?v=" in link:
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
        elif "imgur" in link and link_extension in ("gifv", "GIFV"):
            formatted.append(_gifv_embed(link))
        else:
            formatted.append('<a href="{}">{}</a>'.format(link, link))

        last_match = span[1]

    formatted.append(message[last_match:])
    return "".join(formatted)
