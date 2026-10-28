from zaizai.placement import next_room_name, pick_category

T = "排位房 {n}"


def test_pick_first_non_full():
    assert pick_category([45, 10], 45) == 1


def test_pick_none_when_all_full():
    assert pick_category([45, 45, 45], 45) is None


def test_pick_none_when_no_categories():
    assert pick_category([], 45) is None


def test_next_name_fills_gap():
    assert next_room_name(T, ["排位房 1", "排位房 3"]) == "排位房 2"


def test_next_name_ignores_other_templates():
    assert next_room_name(T, ["匹配房 1", "排位房 1x", "排位房 a"]) == "排位房 1"


def test_next_name_beyond_99():
    names = [f"排位房 {i}" for i in range(1, 100)]
    assert next_room_name(T, names) == "排位房 100"
