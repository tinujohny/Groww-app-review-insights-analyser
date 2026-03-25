import textwrap

from phase2.collectors.app_store_rss import parse_feed_xml


def test_parse_minimal_app_store_feed():
    xml = textwrap.dedent(
        """\
        <?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss">
          <entry>
            <id>12345</id>
            <updated>2024-06-10T12:00:00-07:00</updated>
            <im:rating>5</im:rating>
            <content type="text">one two three four five words in this test review body</content>
          </entry>
        </feed>
        """
    )
    _root, rows = parse_feed_xml(xml.encode("utf-8"))
    assert len(rows) == 1
    assert rows[0]["rating"] == 5
    assert "five words" in rows[0]["text"]
