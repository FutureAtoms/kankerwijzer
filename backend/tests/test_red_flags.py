from app.safety.red_flags import check_red_flags


def test_red_flag_detects_blood_coughing_inflections():
    flag_type, message = check_red_flags("Ik heb bloed opgehoest, wat moet ik doen?")

    assert flag_type == "emergency"
    assert message is not None


def test_red_flag_detects_blood_coughing_word_order_variants():
    flag_type, _ = check_red_flags("Ik hoest bloed op sinds vanochtend.")

    assert flag_type == "emergency"
