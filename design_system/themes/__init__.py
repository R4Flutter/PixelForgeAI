from dataclasses import dataclass

from design_system.tokens import Colors, Elevation, Spacing, Typography


@dataclass(frozen=True)
class DarkTheme:
    spacing: Spacing = Spacing()
    colors: Colors = Colors()
    typography: Typography = Typography()
    elevation: Elevation = Elevation()
    name: str = "dark"


@dataclass(frozen=True)
class LightTheme:
    spacing: Spacing = Spacing()
    colors: Colors = Colors(
        bg_primary="#FFFFFF",
        bg_secondary="#F8F9FA",
        bg_card="#F0F1F3",
        bg_surface="#E8E9ED",
        bg_hover="#DCDEE3",
        bg_active="#D0D2D9",
        text_primary="#1A1D2B",
        text_secondary="#5A6080",
        text_muted="#8A90A6",
        border="#D0D2D9",
        border_hover="#B0B3B9",
    )
    typography: Typography = Typography()
    elevation: Elevation = Elevation()
    name: str = "light"
