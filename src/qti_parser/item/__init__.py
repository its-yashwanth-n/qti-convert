""" QTI Assessment Item """

from lxml import etree
from logzero import logger
import re
import hashlib
import config
from qti_parser import question_type


def _parse_image_href(raw_href):
    """Strip IMS base prefix and detect whether the href is an external URL."""
    href = re.sub(r"\?.+$", "", raw_href)
    href = href.replace(config.img_href_ims_base, "").replace(config.img_href_ims_base_dollar, "")
    is_external = href.startswith("http://") or href.startswith("https://")
    return href, is_external


def get_question(xml_item):
    """ Get question, metadata and answers/options """
    xml_item_metadata = xml_item.find("{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}itemmetadata/{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}qtimetadata")
    this_question = {
        'id': str(xml_item.get("ident")),
        'title': str(xml_item.get("title")),
        'question_type': xml_item_metadata.find("{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}qtimetadatafield[{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}fieldlabel = 'question_type']/{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}fieldentry").text,
        'points_possible': xml_item_metadata.find("{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}qtimetadatafield[{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}fieldlabel = 'points_possible']/{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}fieldentry").text,
        'text': xml_item.find("{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}presentation/{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}material/{http://www.imsglobal.org/xsd/ims_qtiasiv1p2}mattext").text
    }

    image = []

    if this_question['text'] and '<img' in this_question['text'].lower():
        # Extract every img src regardless of surrounding markup
        for match in re.finditer(r'<img[^>]+src="([^"]+)"[^>]*>', this_question['text'], re.DOTALL | re.IGNORECASE):
            href, is_external = _parse_image_href(match.group(1))
            image.append({
                'id': str(hashlib.md5(href.encode()).hexdigest()),
                'href': href,
                'is_external': is_external
            })
        # Remove <p> blocks whose only content is an img, then strip any remaining img tags
        this_question['text'] = re.sub(r'<p>\s*<img[^>]*>\s*</p>', '', this_question['text'], flags=re.DOTALL | re.IGNORECASE)
        this_question['text'] = re.sub(r'<img[^>]*>', '', this_question['text'], flags=re.DOTALL | re.IGNORECASE)

    if image:
        this_question['image'] = image

    # Parse answers for each type of question
    if this_question['question_type'] == "multiple_choice_question":
        this_question['answer'] = question_type.multiple_choice.get_answers(xml_item)
    elif this_question['question_type'] == "true_false_question":
        this_question['answer'] = question_type.true_false.get_answers(xml_item)
    elif this_question['question_type'] == "multiple_answers_question":
        this_question['answer'] = question_type.multiple_answers.get_answers(xml_item)
    elif this_question['question_type'] == "short_answer_question":
        this_question['answer'] = question_type.short_answer.get_answers(xml_item)
    elif this_question['question_type'] == "fill_in_multiple_blanks_question":
        this_question['answer'] = question_type.fill_in_multiple_blanks.get_answers(xml_item)
    elif this_question['question_type'] == "multiple_dropdowns_question":
        this_question['answer'] = question_type.multiple_dropdowns.get_answers(xml_item)
    elif this_question['question_type'] == "matching_question":
        this_question['answer'] = question_type.matching.get_answers(xml_item)
    elif this_question['question_type'] == "numerical_question":
        this_question['answer'] = question_type.numerical.get_answers(xml_item)
    elif this_question['question_type'] == "calculated_question":
        this_question['answer'] = question_type.calculated.get_answers(xml_item)

    # Replace [variable] in question text with blanks
    if (this_question['question_type'] == "fill_in_multiple_blanks_question" or this_question['question_type'] == "multiple_dropdowns_question") and this_question['text'].find(r"\[(.*?)\]"):
        blank = config.blanks_replace_str * config.blanks_question_n
        p = re.compile(r"\[(.*?)\]")
        subn_tuple = p.subn(blank, this_question['text'])
        if subn_tuple[1] > 0:
            this_question['text'] = subn_tuple[0]
        if this_question['question_type'] == "multiple_dropdowns_question":
            this_question['text'] = question_type.multiple_dropdowns.enumerate_blanks(this_question['text'])

    if this_question['question_type'] == "calculated_question":
        if config.calculated_display_var_set_in_text:
            this_question['text'] = question_type.calculated.substitute_variables_in_question(this_question['text'], this_question['answer'][0])

    return this_question
