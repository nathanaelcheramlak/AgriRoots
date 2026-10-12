SORGHUM_DISPLAY_NAMES = {
    "Normal_Sorghum": "Normal sorghum",
    "Anthracnose_Red_Rot": "Anthracnose / Red rot",
    "Cereal_Grain_Molds": "Cereal grain molds",
    "Covered_Kernel_Smut": "Covered kernel smut",
    "Head_Smut": "Head smut",
    "Loose_Smut": "Loose smut",
    "Rust": "Rust",
}


def display_sorghum_class(class_name: str) -> str:
    return SORGHUM_DISPLAY_NAMES.get(class_name, class_name.replace("_", " "))
