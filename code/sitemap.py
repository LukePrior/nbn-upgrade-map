import xml.etree.ElementTree as ET
import utils


def generate_sitemap(json_file, output_file):
    # Load suburbs data from JSON file
    data = utils.read_json_file(json_file)

    # Create the root element for the XML sitemap
    urlset = ET.Element('urlset', xmlns="http://www.sitemaps.org/schemas/sitemap-image/1.1")

    # Add the static stats page without a lastmod tag
    add_url(urlset, "https://nbn.lukeprior.com/stats")

    # Generate URLs for each suburb
    for state, suburbs in data.items():
        for suburb in suburbs:
            suburb_name = suburb['name']
            processed_date = suburb['processed_date']
            url = f"https://nbn.lukeprior.com/?suburb={suburb_name.lower().replace(' ', '-')}&state={state.lower()}"
            add_url(urlset, url, processed_date)

    # Convert the XML tree to a string
    sitemap_xml = ET.tostring(urlset, encoding='utf-8', xml_declaration=True).decode('utf-8')

    # Save the XML to a file
    with open(output_file, 'w') as f:
        f.write(sitemap_xml)


def add_url(urlset, loc, lastmod=None):
    url = ET.SubElement(urlset, 'url')
    loc_element = ET.SubElement(url, 'loc')
    loc_element.text = loc
    if lastmod:
        lastmod_element = ET.SubElement(url, 'lastmod')
        lastmod_element.text = lastmod


generate_sitemap('results/combined-suburbs.json', 'site/sitemap.xml')
