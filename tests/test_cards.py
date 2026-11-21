from pathlib import Path
import app.payment_service as service
import pytest
import json


BASE_DIR = Path(__file__).resolve().parent
json_path = BASE_DIR / "test_cards.json"


with open(json_path, "r") as f:
    cards_data = json.load(f)



@pytest.mark.parametrize(
    "card_number",
    [(c["number"]) for c in cards_data]
)
def test_validateCard_ValidCards_ReturnsTrue(card_number):

    #arrange
    test_card_number=card_number

    #act
    result=service.validateCard(card_number)

    #assert
    assert result==True
@pytest.mark.parametrize(
    "card_number, expected_type",
    [(c["number"], c["type"]) for c in cards_data]
)
def test_getCardType_ValidCards_ReturnsExpectedType(card_number, expected_type):

    #arrange
    test_card_number=card_number

    #act
    result = service.getCardType(test_card_number)

    #assert
    assert result==expected_type