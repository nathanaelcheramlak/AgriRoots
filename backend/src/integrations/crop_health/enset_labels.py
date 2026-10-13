ENSET_DISPLAY_NAMES = {
    "BacterialWilt": "Bacterial Wilt",
    "CormRotk": "Corm Rot",
    "FusariumWilt": "Fusarium Wilt",
    "HealthyEnsetDataset": "Healthy Enset",
    "LeafSpot": "Leaf Spot",
    "SheathRot": "Sheath Rot",
}

def display_enset_class(class_name: str) -> str:
    return ENSET_DISPLAY_NAMES.get(class_name, class_name.replace("_", " "))