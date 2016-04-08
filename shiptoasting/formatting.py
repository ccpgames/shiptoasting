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


def _gifv_embed(gifv_link):
    """Returns a video link to imgur for the gifv."""

    img_id = gifv_link.split(".")[-2].split("/")[-1]
    return """
<video poster="https://i.imgur.com/{id}h.jpg" preload="auto" autoplay="autoplay" muted="muted" loop="loop" width="500" height="370">
<source src="https://i.imgur.com/{id}.mp4" type="video/mp4">
<object type="application/x-shockwave-flash" height="370" width="500" data="https://s.imgur.com/include/flash/gifplayer.swf?imgur_video=https://i.imgur.com/{id}.mp4&imgur_width=500&imgur_height=370">
<param name="movie" value="https://s.imgur.com/include/flash/gifplayer.swf?imgur_video=https://i.imgur.com/{id}.mp4&imgur_width=500&imgur_height=370" />
<param name="allowscriptaccess" value="never" />
<param name="flashvars" value="height=370&amp;width=500" />
<param name="width" value="500" />
<param name="height" value="370" />
<param name="version" value="0" />
<param name="scale" value="scale" />
<param name="salign" value="tl" />
<param name="wmode" value="opaque" />
</object>
</video>
""".format(
    id=img_id
)  # noqa


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
        elif "imgur" in link and link_extension in ("gifv", "GIFV"):
            formatted.append(_gifv_embed(link))
        else:
            formatted.append('<a href="{}">{}</a>'.format(link, link))

        last_match = span[1]

    formatted.append(message[last_match:])
    return "".join(formatted)
