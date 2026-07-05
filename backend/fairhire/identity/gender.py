from transformers import pipeline

_pipeline = None

LABEL_MAP = {"LABEL_0": "female", "LABEL_1": "male"}


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = pipeline(
            "text-classification",
            model="imranali291/genderize",
            device=-1,
        )
    return _pipeline


def predict_gender(first_name: str) -> tuple[str, float]:
    pipe = _get_pipeline()
    result = pipe(first_name)[0]
    gender = LABEL_MAP.get(result["label"], result["label"])
    return gender, result["score"]
