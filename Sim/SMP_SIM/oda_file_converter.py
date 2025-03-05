import os
import subprocess
import platform
import tempfile
import logging
import shutil
from PyQt5.QtWidgets import (
    QMessageBox, QFileDialog, QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QProgressBar, QComboBox, QRadioButton, QTextEdit
)

logger = logging.getLogger(__name__)

ODA_PATHS = {
    'Windows': [r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"],
    'Darwin': ["/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter"],
    'Linux': ["/opt/oda/ODAFileConverter"]
}

def find_oda_converter():
    """Locate ODA File Converter executable."""
    system = platform.system()
    for path in ODA_PATHS.get(system, []):
        if os.path.exists(path):
            return path
    try:
        cmd = 'where' if system == 'Windows' else 'which'
        result = subprocess.run([cmd, 'ODAFileConverter'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split('\n')[0]
    except:
        return None

def convert_cad_to_dxf(input_file, output_file=None, version="ACAD2018", progress_callback=None):
    """Convert CAD to DXF using multiple methods."""
    if not os.path.exists(input_file):
        logger.error(f"Input file missing: {input_file}")
        return False
    if output_file is None:
        output_file = os.path.splitext(input_file)[0] + ".dxf"
    
    # Try ODA
    oda_path = find_oda_converter()
    if oda_path and _convert_using_oda(input_file, output_file, oda_path, version, progress_callback):
        return True
    
    # Try LibreCAD
    if convert_cad_using_librecad(input_file, output_file, progress_callback):
        return True
    
    # Try FreeCAD
    if convert_cad_using_freecad(input_file, output_file, progress_callback):
        return True
    
    # Try python-dwg
    if input_file.lower().endswith('.dwg') and _try_dwg_lib_fallback(input_file, output_file, progress_callback):
        return True
    
    logger.warning("All conversion methods failed")
    if progress_callback:
        progress_callback(100, "Conversion failed")
    return False

def _convert_using_oda(input_file, output_file, oda_path, version, progress_callback):
    """Convert using ODA File Converter."""
    try:
        temp_in_dir = tempfile.mkdtemp()
        temp_out_dir = tempfile.mkdtemp()
        temp_input = os.path.join(temp_in_dir, os.path.basename(input_file))
        shutil.copy2(input_file, temp_input)
        
        cmd = [oda_path, temp_in_dir, temp_out_dir, "ACAD", version, "DXF", version, "0", "1", "1"] if platform.system() == 'Windows' else \
              [oda_path, "--input", temp_in_dir, "--output", temp_out_dir, "--input-format", "ACAD", "--input-version", version, 
               "--output-format", "DXF", "--output-version", version]
        
        if progress_callback:
            progress_callback(30, "Running ODA converter")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        expected_output = os.path.join(temp_out_dir, os.path.splitext(os.path.basename(input_file))[0] + '.dxf')
        if os.path.exists(expected_output):
            shutil.copy2(expected_output, output_file)
            logger.info(f"ODA conversion successful")
            if progress_callback:
                progress_callback(100, "Conversion complete")
            shutil.rmtree(temp_in_dir, ignore_errors=True)
            shutil.rmtree(temp_out_dir, ignore_errors=True)
            return True
        return False
    except Exception as e:
        logger.error(f"ODA conversion error: {e}")
        return False

def convert_cad_using_librecad(input_file, output_file, progress_callback=None):
    """Convert using LibreCAD."""
    librecad_paths = {
        'Windows': [r"C:\Program Files\LibreCAD\librecad.exe"],
        'Linux': ["/usr/bin/librecad"]
    }
    system = platform.system()
    for path in librecad_paths.get(system, []):
        if os.path.exists(path):
            try:
                if progress_callback:
                    progress_callback(30, "Running LibreCAD")
                cmd = [path, '-c', input_file, output_file]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    logger.info(f"LibreCAD conversion successful")
                    if progress_callback:
                        progress_callback(100, "Conversion complete")
                    return True
            except Exception as e:
                logger.error(f"LibreCAD error: {e}")
    return False

def convert_cad_using_freecad(input_file, output_file, progress_callback=None):
    """Convert using FreeCAD."""
    freecad_paths = {
        'Windows': [r"C:\Program Files\FreeCAD\bin\FreeCAD.exe"],
        'Linux': ["/usr/bin/freecad"]
    }
    system = platform.system()
    for path in freecad_paths.get(system, []):
        if os.path.exists(path):
            try:
                script = f"import FreeCAD; import ImportDXF; doc = FreeCAD.openDocument('{input_file.replace('\\', '\\\\')}'); ImportDXF.export([doc.Objects], '{output_file.replace('\\', '\\\\')}')"
                script_path = os.path.join(tempfile.gettempdir(), "freecad_convert.py")
                with open(script_path, 'w') as f:
                    f.write(script)
                if progress_callback:
                    progress_callback(50, "Running FreeCAD")
                cmd = [path, '-c', script_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                os.remove(script_path)
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    logger.info(f"FreeCAD conversion successful")
                    if progress_callback:
                        progress_callback(100, "Conversion complete")
                    return True
            except Exception as e:
                logger.error(f"FreeCAD error: {e}")
    return False

def _try_dwg_lib_fallback(input_file, output_file, progress_callback):
    """Fallback using ezdxf library."""
    try:
        import importlib.util
        dwg_spec = importlib.util.find_spec("ezdxf")
        if dwg_spec is None:
            logger.info("ezdxf module not installed, skipping this conversion method")
            return False
        
        try:
            def _do_dwg_conversion():
                import ezdxf as dwg_module  # type: ignore[import]
                doc = dwg_module.readfile(input_file)
                doc.saveas(output_file)  # ezdxf uses saveas for DXF
                return True
            
            if progress_callback:
                progress_callback(80, "Using ezdxf")
            
            success = _do_dwg_conversion()
            if success and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                logger.info(f"ezdxf conversion successful")
                if progress_callback:
                    progress_callback(100, "Conversion complete")
                return True
        except ImportError:
            logger.warning("Failed to import ezdxf even though it was detected")
            return False
    except Exception as e:
        logger.error(f"ezdxf error: {e}")
    return False

class EnhancedConversionDialog(QDialog):
    """Dialog for CAD file conversion."""
    def __init__(self, input_file=None, parent=None):
        super().__init__(parent)
        self.input_file = input_file
        self.output_file = None
        self.converted = False
        self.setWindowTitle("CAD File Conversion")
        self.setMinimumWidth(550)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Convert your CAD file to DXF or SVG for simulation use."))
        
        if not input_file:
            self.file_button = QPushButton("Select CAD File")
            self.file_button.clicked.connect(self.select_input_file)
            layout.addWidget(self.file_button)
        else:
            layout.addWidget(QLabel(f"File: {os.path.basename(input_file)}"))
        
        layout.addWidget(QLabel("Target Format:"))
        format_layout = QHBoxLayout()
        self.format_dxf = QRadioButton("DXF")
        self.format_dxf.setChecked(True)
        self.format_svg = QRadioButton("SVG")
        format_layout.addWidget(self.format_dxf)
        format_layout.addWidget(self.format_svg)
        layout.addLayout(format_layout)
        
        layout.addWidget(QLabel("DXF Version:"))
        self.version_combo = QComboBox()
        self.version_combo.addItems(["AutoCAD 2018", "AutoCAD 2013", "AutoCAD 2010"])
        layout.addWidget(self.version_combo)
        
        self.format_dxf.toggled.connect(lambda checked: self.version_combo.setEnabled(checked))
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMinimumHeight(100)
        layout.addWidget(self.detail_text)
        
        button_layout = QHBoxLayout()
        self.convert_button = QPushButton("Convert")
        self.convert_button.clicked.connect(self.start_conversion)
        self.convert_button.setEnabled(bool(input_file))
        button_layout.addWidget(self.convert_button)
        
        self.manual_button = QPushButton("Manual Guide")
        self.manual_button.clicked.connect(self.show_manual_guide)
        button_layout.addWidget(self.manual_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def select_input_file(self):
        """Select input CAD file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select CAD File", "", "CAD Files (*.dwg *.dxf *.cad *.svg);;All Files (*)")
        if file_path:
            self.input_file = file_path
            layout = self.layout()
            idx = layout.indexOf(self.file_button)
            layout.removeWidget(self.file_button)
            self.file_button.deleteLater()
            layout.insertWidget(idx, QLabel(f"File: {os.path.basename(file_path)}"))
            self.convert_button.setEnabled(True)
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.svg':
                self.format_svg.setChecked(True)

    def start_conversion(self):
        """Initiate conversion process."""
        if not self.input_file:
            return
        output_format = "dxf" if self.format_dxf.isChecked() else "svg"
        self.output_file = os.path.splitext(self.input_file)[0] + f".{output_format}"
        
        if os.path.exists(self.output_file):
            if QMessageBox.question(self, "File Exists", "Overwrite existing file?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
                new_output, _ = QFileDialog.getSaveFileName(self, "Save As", "", f"{output_format.upper()} Files (*.{output_format})")
                if not new_output:
                    return
                self.output_file = new_output
        
        self.convert_button.setEnabled(False)
        self.manual_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.detail_text.clear()
        self.status_label.setText("Converting...")
        self.progress_bar.setValue(10)
        
        success = False
        if output_format == "dxf":
            version = {"AutoCAD 2018": "ACAD2018", "AutoCAD 2013": "ACAD2013", "AutoCAD 2010": "ACAD2010"}[self.version_combo.currentText()]
            success = convert_cad_to_dxf(self.input_file, self.output_file, version, self.update_progress)
        elif output_format == "svg":
            if self.input_file.lower().endswith(('.dwg', '.cad')):
                temp_dxf = os.path.join(tempfile.gettempdir(), "temp.dxf")
                if convert_cad_to_dxf(self.input_file, temp_dxf, progress_callback=self.update_progress):
                    success = self._convert_dxf_to_svg(temp_dxf, self.output_file)
            elif self.input_file.lower().endswith('.dxf'):
                success = self._convert_dxf_to_svg(self.input_file, self.output_file)
        
        self.convert_button.setEnabled(True)
        self.manual_button.setEnabled(True)
        self.close_button.setEnabled(True)
        
        if success:
            self.status_label.setText("Conversion successful")
            self.detail_text.append(f"Output saved to: {self.output_file}")
            QMessageBox.information(self, "Success", f"Converted to {self.output_file}")
            self.converted = True
        else:
            self.status_label.setText("Conversion failed")
            QMessageBox.warning(self, "Failed", "Conversion failed. Try manual conversion.")

    def _convert_dxf_to_svg(self, dxf_file, svg_file):
        """Convert DXF to SVG."""
        try:
            # Try to import ezdxf - it should be installed for this function to work
            import ezdxf
            doc = ezdxf.readfile(dxf_file)
            msp = doc.modelspace()
            min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
            
            for entity in msp:
                if entity.dxftype() == 'LINE':
                    min_x = min(min_x, entity.dxf.start.x, entity.dxf.end.x)
                    min_y = min(min_y, entity.dxf.start.y, entity.dxf.end.y)
                    max_x = max(max_x, entity.dxf.start.x, entity.dxf.end.x)
                    max_y = max(max_y, entity.dxf.start.y, entity.dxf.end.y)
                elif entity.dxftype() == 'CIRCLE':
                    min_x = min(min_x, entity.dxf.center.x - entity.dxf.radius)
                    min_y = min(min_y, entity.dxf.center.y - entity.dxf.radius)
                    max_x = max(max_x, entity.dxf.center.x + entity.dxf.radius)
                    max_y = max(max_y, entity.dxf.center.y + entity.dxf.radius)
            
            if min_x == float('inf'):
                min_x, min_y, max_x, max_y = 0, 0, 1000, 1000
            width = max_x - min_x
            height = max_y - min_y
            margin = max(width, height) * 0.1
            min_x -= margin
            min_y -= margin
            width += 2 * margin
            height += 2 * margin
            
            with open(svg_file, 'w') as f:
                f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x} {min_y} {width} {height}">\n')
                for entity in msp:
                    if entity.dxftype() == 'LINE':
                        f.write(f'<line x1="{entity.dxf.start.x}" y1="{entity.dxf.start.y}" x2="{entity.dxf.end.x}" y2="{entity.dxf.end.y}" stroke="black" stroke-width="1"/>\n')
                    elif entity.dxftype() == 'CIRCLE':
                        f.write(f'<circle cx="{entity.dxf.center.x}" cy="{entity.dxf.center.y}" r="{entity.dxf.radius}" stroke="black" fill="none" stroke-width="1"/>\n')
                f.write('</svg>')
            self.update_progress(100, "SVG conversion complete")
            return True
        except ImportError:
            logger.error("ezdxf library not found. Cannot convert DXF to SVG.")
            self.detail_text.append("Error: ezdxf library not found. Install it with 'pip install ezdxf'")
            return False
        except Exception as e:
            logger.error(f"DXF to SVG error: {e}")
            self.detail_text.append(f"Error converting to SVG: {e}")
            return False

    def update_progress(self, percent, message):
        """Update progress UI."""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
        self.detail_text.append(message)

    def show_manual_guide(self):
        """Show manual conversion guide."""
        QMessageBox.information(self, "Manual Guide", 
                                "Convert manually:\n1. AutoCAD: 'Save As' DXF\n2. Free tools: ODA, FreeCAD, LibreCAD\n3. SVG: Use Inkscape after DXF conversion")

    def get_result(self):
        """Return conversion result."""
        return self.output_file if self.converted else None

def show_conversion_dialog(sim_service=None, parent=None):
    """
    Show the CAD conversion dialog.
    
    Args:
        sim_service: SimulationService instance (optional)
        parent: Parent widget (optional)
        
    Returns:
        bool: True if conversion was successful, False otherwise
    """
    dialog = EnhancedConversionDialog(parent=parent)
    dialog.exec_()
    result = dialog.get_result()
    
    if result and sim_service and hasattr(sim_service, 'cad_background'):
        # Update the CAD background with the new file
        sim_service.cad_background.cad_file_path = result
        sim_service.cad_background.create_background()
        sim_service.cad_background.setup_layer_management()
        return True
    
    return bool(result)