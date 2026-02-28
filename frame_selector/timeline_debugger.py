"""
Timeline Debugger - Introspection module for Krita's Timeline Docker.

This module attempts to access Krita's internal Timeline Docker selection
state via Qt introspection, since the official Python API doesn't expose
this directly.

The goal is to detect when the Timeline selection (row = layer, column = frame)
doesn't match the active layer from the Layers Panel (doc.activeNode()).

Usage:
    from .timeline_debugger import TimelineDebugger
    info = TimelineDebugger.get_timeline_selection_info()
    print(info)
"""

from typing import Dict, Any, Optional


class TimelineDebugger:
    """
    Timeline selection introspection via Qt dockers.
    
    Krita's Timeline Docker is a Qt dock widget that contains internal
    selection state we need to access for validation.
    """
    
    # Known object names/class names for the Timeline Docker components
    TIMELINE_DOCKER_NAMES = [
        "TimelineDocker",
        "Animation Timeline", 
        "timeline_dock",
    ]
    
    @staticmethod
    def get_timeline_selection_info() -> Dict[str, Any]:
        """
        Attempt to retrieve the current timeline selection.
        
        Returns a dict with:
        - 'docker_found': bool - whether we found the timeline docker
        - 'selection': dict with 'row' (layer), 'column' (frame), or None
        - 'error': error message if something failed
        - 'debug_info': raw internal data for investigation
        """
        result = {
            'docker_found': False,
            'selection': None,
            'error': None,
            'debug_info': {},
        }
        
        try:
            from krita import Krita
        except ImportError:
            result['error'] = "Krita module not available (not running in Krita?)"
            return result
        
        # Get all dockers
        dockers = Krita.instance().dockers()
        
        # Find the Timeline Docker
        timeline_docker = None
        for docker in dockers:
            docker_name = docker.objectName() if hasattr(docker, 'objectName') else ""
            window_title = docker.windowTitle() if hasattr(docker, 'windowTitle') else ""
            
            # Check if this is the timeline docker
            is_timeline = (
                "timeline" in docker_name.lower() or 
                "timeline" in window_title.lower() or
                "Animation" in window_title
            )
            
            if is_timeline:
                timeline_docker = docker
                result['debug_info']['docker_name'] = docker_name
                result['debug_info']['window_title'] = window_title
                break
        
        if not timeline_docker:
            result['error'] = "Timeline Docker not found in open dockers"
            # List all dockers for debugging
            result['debug_info']['available_dockers'] = [
                {
                    'name': d.objectName() if hasattr(d, 'objectName') else "???",
                    'title': d.windowTitle() if hasattr(d, 'windowTitle') else "???"
                }
                for d in dockers
            ]
            return result
        
        result['docker_found'] = True
        
        # Now explore the timeline docker's internal structure
        # We'll use Qt's findChildren to look for selection-related widgets
        TimelineDebugger._explore_timeline_internals(
            timeline_docker, result
        )
        
        return result
    
    @staticmethod
    def _explore_timeline_internals(
        docker, result: Dict[str, Any]
    ) -> None:
        """
        Explore the internal Qt structure of the timeline docker
        to find the selection model.
        """
        from PyQt5.QtWidgets import QAbstractItemView
        from PyQt5.QtCore import Qt
        
        debug = result['debug_info']
        debug['children_count'] = docker.children().__len__()
        
        # Look for QAbstractItemView (table/tree views)
        views = docker.findChildren(QAbstractItemView)
        
        debug['item_views_found'] = len(views)
        debug['item_views'] = []
        
        for i, view in enumerate(views):
            view_info = {
                'index': i,
                'class': view.__class__.__name__,
                'object_name': view.objectName() if hasattr(view, 'objectName') else "",
            }
            
            # Try to get selection model
            selection_model = view.selectionModel()
            if selection_model:
                selected_indexes = selection_model.selectedIndexes()
                view_info['selection_count'] = len(selected_indexes)
                
                if selected_indexes:
                    # Get the first selection (row, column)
                    first = selected_indexes[0]
                    view_info['selected_row'] = first.row()
                    view_info['selected_column'] = first.column()
                    
                    # Try to get the model
                    model = view.model()
                    if model:
                        # Get layer name from row (if it's a tree/table model)
                        try:
                            if hasattr(model, 'index'):
                                idx = model.index(first.row(), 0)
                                if idx.isValid():
                                    view_info['row_data'] = str(model.data(idx))
                                    # Qt ItemDataRole for internal object
                                    # We can sometimes extract internal pointers or names here
                                    view_info['display_role'] = str(model.data(idx, Qt.DisplayRole))
                        except Exception as e:
                            view_info['row_data_error'] = str(e)
                
                # Store selection if we found it
                if result['selection'] is None and 'selected_row' in view_info:
                    result['selection'] = {
                        'row': view_info['selected_row'],
                        'column': view_info.get('selected_column', 0),
                        'view_class': view.__class__.__name__,
                        'layer_name_guess': view_info.get('display_role', 'Unknown')
                    }
            
            debug['item_views'].append(view_info)
    
    @staticmethod
    def get_timeline_layer_order() -> Dict[str, int]:
        """
        Recursively traverse the Krita layer tree to map Layer UUID -> Timeline Row Index.
        The Timeline displays layers top-down, skipping groups (unless animated? TBD).
        """
        try:
            from krita import Krita
        except ImportError:
            return {}

        doc = Krita.instance().activeDocument()
        if not doc:
            return {}

        layer_order = {}
        current_row = 0

        # Krita's Timeline usually ignores the root node and displays top-level layers downwards
        # We need to traverse exactly how the Timeline model does.
        # This function might need tuning based on how Krita flattens groups in the Timeline.
        def traverse_node(node):
            nonlocal current_row
            
            layer_order[node.uniqueId().toString()] = {
                'row': current_row,
                'name': node.name(),
                'type': node.type()
            }
            current_row += 1
            
            # Krita returns children bottom-to-top (z-index order).
            # The Timeline displays top-to-bottom.
            # So we iterate children in REVERSE to match the UI.
            children = reversed(node.childNodes())
            for child in children:
                traverse_node(child)

        root = doc.rootNode()
        if root:
            # We reverse the top level children so the topmost visual layer gets row 0
            for child in reversed(root.childNodes()):
                traverse_node(child)

        return layer_order
    
    @staticmethod
    def validate_clone_target() -> Dict[str, Any]:
        """
        Main validation function: compares Timeline selection vs Active Layer.
        
        This is what we ultimately want: detect when the user has clicked
        on a different layer in the Timeline than what's active in the
        Layers Panel.
        
        Returns:
        - 'match': bool - whether Timeline row matches active layer
        - 'timeline_layer_info': info from timeline selection
        - 'active_layer_info': info from doc.activeNode()
        - 'warning': message to show user if there's a mismatch
        """
        validation = {
            'match': False,
            'timeline_layer_info': None,
            'active_layer_info': None,
            'warning': None,
        }
        
        try:
            from krita import Krita
        except ImportError:
            validation['warning'] = "Not running in Krita"
            return validation
        
        # Get active layer from document
        doc = Krita.instance().activeDocument()
        if not doc:
            validation['warning'] = "No active document"
            return validation
        
        active_node = doc.activeNode()
        if active_node:
            validation['active_layer_info'] = {
                'name': active_node.name(),
                'unique_id': active_node.uniqueId().toString(),
                'type': active_node.type(),
            }
        
        # Get timeline selection info
        timeline_info = TimelineDebugger.get_timeline_selection_info()
        
        # Build layer order mapping
        layer_order = TimelineDebugger.get_timeline_layer_order()
        
        # Check active node against the mapped order
        active_layer_row = -1
        if active_node and active_node.uniqueId().toString() in layer_order:
            order_data = layer_order[active_node.uniqueId().toString()]
            if isinstance(order_data, dict) and 'row' in order_data:
                active_layer_row = int(order_data['row'])
                active_info = validation['active_layer_info']
                if isinstance(active_info, dict):
                    active_info['mapped_timeline_row'] = active_layer_row
        
        if timeline_info['selection']:
            validation['timeline_layer_info'] = timeline_info['selection']
            
            # The core check: Does the selected timeline row match the calculated row for the active layer?
            timeline_row = timeline_info['selection']['row']
            
            validation['match'] = (timeline_row == active_layer_row)
            
            if not validation['match']:
                validation['warning'] = (
                    f"Timeline mismatch!\n"
                    f"Active layer '{active_node.name()}' is row {active_layer_row}, "
                    f"but Timeline is selecting row {timeline_row}."
                )
            
            validation['debug_timeline'] = timeline_info
        
        validation['layer_order_map'] = layer_order
        return validation
    
    @staticmethod
    def get_formatted_info() -> str:
        """
        Get a human-readable string with timeline selection info.
        Useful for showing in a QMessageBox.
        """
        val = TimelineDebugger.validate_clone_target()
        info = val.get('debug_timeline', TimelineDebugger.get_timeline_selection_info())
        
        lines = []
        lines.append("=== Timeline Sync Status ===")
        
        if val.get('match'):
            lines.append("✅ Timeline and Active Layer are SYNCED")
        else:
            lines.append("❌ Timeline and Active Layer MISMATCH!")
            if val.get('warning'):
                lines.append(f"   {val['warning']}")
                
        lines.append("\n=== Active Layer (Doc) ===")
        if val.get('active_layer_info'):
            al = val['active_layer_info']
            lines.append(f"Name: {al.get('name')}")
            lines.append(f"UUID: {al.get('unique_id')}")
            lines.append(f"Mapped Row: {al.get('mapped_timeline_row')}")
        else:
            lines.append("None selected")
            
        lines.append("\n=== Timeline Selection ===")
        
        if info['error']:
            lines.append(f"❌ Error: {info['error']}")
        else:
            if info['selection']:
                sel = info['selection']
                lines.append(f"Row: {sel['row']}")
                lines.append(f"Column (Frame): {sel['column']}")
                lines.append(f"Guessed Layer Name: {sel.get('layer_name_guess', 'Unknown')}")
            else:
                lines.append("⚠️ No selection detected in timeline views")
        
        # Add debug info
        debug = info.get('debug_info', {})
        if 'item_views' in debug:
            lines.append("\n🔍 View details:")
            for v in debug['item_views']:
                if 'selected_row' in v:
                    lines.append(f"   Row={v['selected_row']}, Data='{v.get('row_data', 'N/A')}'")
        
        return "\n".join(lines)
