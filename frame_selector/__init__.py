# Frame Selector - Krita Plugin
# Select and clone animation frames from the timeline

from krita import DockWidgetFactory, DockWidgetFactoryBase

from .frame_selector_docker import FrameSelectorDocker


# Krita plugin entry point - registers the Docker (panel) widget
DOCKER_ID = "frame_selector_docker"

instance = Krita.instance()
dock_widget_factory = DockWidgetFactory(
    DOCKER_ID,
    DockWidgetFactoryBase.DockRight,
    FrameSelectorDocker
)

instance.addDockWidgetFactory(dock_widget_factory)
