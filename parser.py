import logging
import defusedxml.lxml, lxml, re

ALLOWED_SCHEMES = {
    r'http://www\.w3\.org/\d{4}/XMLSchema-instance': 'xsi',
    r'http://www.w3.org/XML/\d{4}/namespace': 'xml',
    r'http://www\.w3\.org/\d{4}/xlink': 'xlink',
    r'http://www\.w3\.org/\d{4}/xhtml': 'xhtml',

    r'http://www\.xbrl\.org/\d{4}/instance.*':'xbrli',
    r'http://www\.xbrl\.org/\d{4}/linkbase': 'xbrll',
    r'http://xbrl\.org/\d{4}/xbrldi':'xbrldi',

    r"http://fasb\.org/us-gaap/\d{4}(\-\d{2}-\d{2})?": 'us-gaap',
    r'http://xbrl\.us/us-gaap/\d{4}-\d{2}-\d{2}': 'us-gaap',

    r'http://xbrl\.sec\.gov/dei/\d{4}(\-\d{2}-\d{2})?': 'dei',
    r'http://xbrl\.us/dei/\d{4}-\d{2}-\d{2}': 'dei',

    r'http://fasb\.org/srt/\d{4}-\d{2}-\d{2}': 'srt',

    r'http://xbrl\.us/invest/\d{4}-\d{2}-\d{2}': 'invest',
    r'http://xbrl\.sec\.gov/invest/\d{4}-\d{2}-\d{2}': 'invest',

    #r'http://imetrix\.edgar-online\.com/\d{8}': 'mmtrs',
    #r'http://www\.xbrl\.org/us/fr/common/pte/\d{4}-\d{2}-\d{2}': 'usfr-pte',
}
FACT_PARSE_NS=['us-gaap', 'dei', 'invest', 'srt']
logger = logging.getLogger(__name__)


def parse_form(raw, name=""):
    try:
        #print(f.url)
        report = xmlbytestodict(raw)
    except:
        logger.exception("can't parse " + name)
        """
        try:
            ud = UnicodeDammit(f.xml.tobytes())
            xml = ud.unicode_markup
            xml = re.sub(
                r'''(<\?xml[^>]*)(\sencoding=['"].+?['"])([^>]*>)''', r'\1\3',
                xml,
                count=1,
                flags=re.MULTILINE | re.DOTALL
            )

            xml = re.sub(
                r"(<[^<]*TextBlock(?:\s[^>]*)?>).*?(<[^<]*TextBlock(?:\s[^>]*)?>)", '',
                xml,
                flags=re.MULTILINE | re.DOTALL
            )
            report = xmlbytestodict(xml)
        except:
            print("parse error", f.url)
            traceback.print_exc()
            return
        """
        return None
    replaced_schemes = dict()
    unmatched_schemes = set()

    def key_filter(key):
        if ':' not in key:
            return key
        pk = key.split(':')
        schema = ":".join(pk[:-1])
        key = pk[-1]

        mapped_schema = next((ALLOWED_SCHEMES[s] for s in ALLOWED_SCHEMES if re.match(s, schema)), None)
        if not mapped_schema:
            unmatched_schemes.add(schema)

        if mapped_schema is not None and mapped_schema not in replaced_schemes:
            replaced_schemes[mapped_schema] = schema

        mapped_key = (mapped_schema + ':' + key) if mapped_schema is not None else None

        return mapped_key

    filtered_report = key_map(report, key_filter)
    facts = extract_facts(filtered_report)

    if len(unmatched_schemes) > 0:
        print("INFO: Not matched schemes: ", unmatched_schemes)
    return {
        "schemes": replaced_schemes,
        "facts": facts
    }


def extract_facts(tree):
    periodDict = dict(
        (c['attrib']['id'].strip(), extract_period(c)) for c in tree['children'] if c['tag'] == 'xbrli:context'
    )

    identifierDict = dict(
        (c['attrib']['id'].strip(), extract_identifier(c)) for c in tree['children'] if c['tag'] == 'xbrli:context'
    )

    segmentDict = dict(
        e for e in (
            (c['attrib']['id'].strip(), extract_segment(c)) for c in tree['children'] if c['tag'] == 'xbrli:context'
        ) if e[1] is not None
    )

    unitDict = dict(
        (c['attrib']['id'], extract_unit(c)) for c in tree['children'] if c['tag'] == 'xbrli:unit'
    )

    facts = [extract_fact(c, identifierDict, periodDict, unitDict, segmentDict) for c in tree['children']
             if ':' in c['tag'] and c['tag'].split(':')[0] in FACT_PARSE_NS
             and (c.get('text') is None or len(c['text']) < 1024)] # not c['tag'].endswith('TextBlock')]

    return facts


def extract_fact(fact, identifierDict, contextDict, unitDict, segmentDict):
    ret = dict()
    ret['name'] = fact['tag']

    contextRef = fact['attrib'].get('contextRef')
    if contextRef is not None:
        contextRef = contextRef.strip()
        ret['identifier'] = identifierDict[contextRef]
        ret['period'] = contextDict[contextRef]
        segment = segmentDict.get(contextRef)
        if segment is not None:
            ret['segment'] = segment

    unitRef = fact['attrib'].get('unitRef')
    if unitRef is not None:
        unitRef = unitRef.strip()
        ret['unit'] = unitDict.get(unitRef)

    decimals = fact['attrib'].get('decimals')
    if decimals is not None:
        ret['decimals'] = 'INF' if decimals == 'INF' else int(decimals)

    if fact['attrib'].get('xsi:nil') == 'true':
        value = None
    else:
        value = fact.get('text')
        if value is not None :
            value = value.strip()
            if value == 'true' or value == 'false':
                value = value == 'true'
            else:
                try:
                    value = int(value)
                except:
                    try:
                        value = float(value)
                    except:
                        pass
        else:
            value = fact['children']
    ret['value'] = value

    return ret


def extract_unit(unit):
    measure = extract_measure(unit)
    if measure is not None:
        return {'type': 'measure', 'value': measure}

    divide = next((c for c in unit['children'] if c['tag'] == 'xbrli:divide'), None)
    if divide is not None:
        unitNumerator = next((c for c in divide['children'] if c['tag'] == 'xbrli:unitNumerator'), None)
        unitNumerator = extract_measure(unitNumerator)
        unitDenominator = next((c for c in divide['children'] if c['tag'] == 'xbrli:unitDenominator'), None)
        unitDenominator = extract_measure(unitDenominator)
        return {'type': 'divide',
                'value': [unitNumerator, unitDenominator]}

    return None


def extract_measure(unit):
    return next((c['text'] for c in unit['children'] if c['tag'] == 'xbrli:measure'), None)


def extract_period(ctx):
    period = next((c for c in ctx['children'] if c['tag'] == 'xbrli:period'), None)

    instant = next((c['text'] for c in period['children'] if c['tag'] == 'xbrli:instant'), None)
    if instant is not None:
        return { 'type': 'instant', 'value': instant}

    startDate = next((c['text'] for c in period['children'] if c['tag'] == 'xbrli:startDate'), None)
    endDate = next((c['text'] for c in period['children'] if c['tag'] == 'xbrli:endDate'), None)

    if startDate is not None and endDate is not None:
        return { 'type': 'range', 'value': [startDate, endDate]}

    forever = next((c for c in period['children'] if c['tag'] == 'xbrli:forever'), None)
    if forever is not None:
        return { 'type': 'forever', 'value': None }

    return None


def extract_identifier(ctx):
    entity = next((c for c in ctx['children'] if c['tag'] == 'xbrli:entity'))
    identifier = next((c for c in entity['children'] if c['tag'] == 'xbrli:identifier'))
    return {'schema':identifier['attrib']['scheme'], 'value': identifier['text'].strip()}


def extract_segment(ctx):
    entity = next((c for c in ctx['children'] if c['tag'] == 'xbrli:entity'))
    segment = next((c for c in entity['children'] if c['tag'] == 'xbrli:segment'), None)

    if segment is None:
        return None

    ss = []
    for s in segment['children']:
        if s['tag'] == 'xbrldi:explicitMember':
            v = s['text']
            if v is not None:
                v = v.strip()
            ss.append({'type': 'explicit', 'dimension':s['attrib']['dimension'], 'value': v.strip()})
        elif s['tag'] == 'xbrldi:typedMember':
            dim = s['attrib']['dimension']
            child = s['children'][0]
            if child['attrib'].get('xsi:nil') == 'true':
                child = None

            ss.append({'type': 'typed', 'dimension':dim, 'value': child})
        else:
            print(s)
    return ss


def key_map(tree, key_mapper):
    if not isinstance(tree, dict):
        return tree

    tag = key_mapper(tree['tag'])
    if tag is None:
        return None

    attrib = tree['attrib']
    attrib = dict(e for e in ((key_mapper(k), attrib[k]) for k in attrib) if e[0] is not None)

    children = [key_map(c, key_mapper) for c in tree['children']]
    children = [c for c in children if c is not None]

    return {
        'tag': tag,
        'attrib': attrib,
        'children': children,
        'text': tree['text']
    }


def xmlbytestodict(xml):
    parser = lxml.etree.XMLParser(remove_comments=True,recover=True)
    root = defusedxml.lxml.XML(xml, parser)
    d = lxmltodict(root)
    return d


def lxmltodict(root):
    if isinstance(root, lxml.etree._Element):
        return {
            'tag': root.tag.replace('{', '').replace('}', ':'),
            'attrib': dict((k.replace('{', '').replace('}', ':'), root.attrib[k]) for k in root.attrib),
            'children': [lxmltodict(c) for c in root],
            'text': root.text.strip() if root.text is not None else None
        }
    else:
        return None

