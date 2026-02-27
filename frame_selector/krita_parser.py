"""
Krita Parser Module.

Este módulo se encarga de la inspección forense de archivos .kra.
Su única responsabilidad es abrir el archivo ZIP, parsear los XML internos
(maindoc.xml y keyframes.xml) y devolver una estructura de datos limpia
sobre qué frames son clones y cuáles son contenido único.

No depende de la API de Krita (LibKis), solo de librerías estándar de Python.
"""

import zipfile
import xml.etree.ElementTree as ET
import os


class KritaParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self._zip = None
        # Los frames vacíos/default en Krita suelen pesar 56 bytes (4 bytes pixel + header)
        # Usamos 100 bytes como umbral de seguridad.
        self.EMPTY_FRAME_THRESHOLD = 100

    def get_layer_clones(self):
        """
        Analiza el archivo y devuelve los clones por capa.
        
        Retorna:
            dict: {
                "layer_uuid": {
                    "layer_name": "Nombre Capa",
                    "clones": [
                        {
                            "source_id": "layer5.f3",   # ID interno del archivo
                            "times": [0, 5, 12],        # Frames donde aparece
                            "is_empty": False           # Si tiene contenido
                        },
                        ...
                    ]
                }
            }
        """
        if not os.path.exists(self.file_path):
            return {}

        try:
            with zipfile.ZipFile(self.file_path, 'r') as z:
                self._zip = z
                
                # 1. Obtener mapa de capas (UUID -> Info Archivo)
                layers_map = self._parse_maindoc()
                
                results = {}
                
                # 2. Procesar cada capa que tenga animación
                for uuid, info in layers_map.items():
                    keyframes_xml = info['keyframes_xml']
                    
                    # Buscar la ruta real dentro del zip (puede estar en carpetas)
                    full_xml_path = self._find_in_zip(keyframes_xml)
                    
                    if full_xml_path:
                        clones = self._parse_layer_keyframes(full_xml_path)
                        
                        # Solo guardamos si encontramos frames válidos
                        if clones:
                            results[uuid] = {
                                "layer_name": info['name'],
                                "clones": clones
                            }
                            
                return results

        except Exception as e:
            print(f"[KritaParser] Error analizando archivo: {e}")
            return {}

    def _parse_maindoc(self):
        """
        Lee maindoc.xml para vincular UUIDs de capas con sus archivos de keyframes.
        """
        layers = {}
        try:
            with self._zip.open('maindoc.xml') as f:
                tree = ET.parse(f)
                
                # Usamos iter() para ser agnósticos a namespaces (xmlns)
                # Krita usa xmlns="http://www.calligra.org/DTD/krita" lo que rompe findall() simple
                for elem in tree.iter():
                    # Buscamos tags que terminen en 'layer' (ej: {namespace}layer o layer)
                    if elem.tag.endswith('layer'):
                        uuid = elem.get('uuid')
                        name = elem.get('name')
                        kf_file = elem.get('keyframes') # Ej: layer5.keyframes.xml
                        
                        if uuid and kf_file:
                            layers[uuid] = {
                                'name': name,
                                'keyframes_xml': kf_file
                            }
        except KeyError:
            pass # maindoc.xml no encontrado
            
        return layers

    def _parse_layer_keyframes(self, xml_path):
        """
        Analiza el XML de una capa específica para agrupar frames por referencia.
        """
        frames_by_source = {} # { "layer5.f3": [0, 10, 20] }
        
        with self._zip.open(xml_path) as f:
            tree = ET.parse(f)
            
            # Usamos iter() para evitar problemas con namespaces de Krita
            for elem in tree.iter():
                if elem.tag.endswith('keyframe'):
                    time_attr = elem.get('time')
                    frame_src = elem.get('frame')
                    
                    if time_attr is not None and frame_src:
                        time = int(time_attr)
                        
                        if frame_src not in frames_by_source:
                            frames_by_source[frame_src] = []
                        frames_by_source[frame_src].append(time)
        
        # Procesar los grupos encontrados
        processed_groups = []
        base_path = os.path.dirname(xml_path)
        
        for src, times in frames_by_source.items():
            # Ruta completa al archivo de imagen para chequear tamaño
            # Si src es "layer5", el archivo suele estar en la misma carpeta que el xml
            # Ojo: a veces src es "layer5" (sin extensión) y el archivo es "layer5.defaultpixel" o similar
            # Pero en los casos de frames animados es "layer5.fXX".
            
            img_path = f"{base_path}/{src}"
            
            # Filtramos los vacíos
            if not self._is_empty_frame(img_path):
                times.sort()
                processed_groups.append({
                    "source_id": src,
                    "times": times,
                    "representative_frame": times[0] # El primer frame para usar de miniatura
                })
                
        # Ordenar por el momento de aparición del primer frame
        processed_groups.sort(key=lambda x: x['times'][0])
        
        return processed_groups

    def _find_in_zip(self, suffix):
        """Encuentra la ruta completa de un archivo dentro del zip dado su nombre final."""
        for name in self._zip.namelist():
            if name.endswith(suffix):
                return name
        return None

    def _is_empty_frame(self, file_path):
        """
        Determina si un frame está vacío basándose en el tamaño del archivo.
        Los frames vacíos o de 'default pixel' suelen pesar < 60 bytes.
        """
        try:
            info = self._zip.getinfo(file_path)
            return info.file_size < self.EMPTY_FRAME_THRESHOLD
        except KeyError:
            # Si el archivo no existe físicamente, puede ser un frame generado
            # o un error de referencia. Ante la duda, lo tratamos como vacío 
            # para no mostrar basura.
            return True
