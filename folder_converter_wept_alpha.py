import os
import sys
import glob
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QWidget, QLabel, QPushButton, QTableWidget, 
                             QTableWidgetItem, QProgressBar, QFileDialog, 
                             QHBoxLayout, QSizePolicy, QHeaderView, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QThreadPool, QRunnable
from PyQt5.QtGui import QPixmap, QFont, QColor
from pathlib import Path
from PIL import Image

# Percorso dell'ambiente virtuale
venv_path = os.path.join(os.getcwd(), 'venv')

# Controlla se l'ambiente virtuale esiste
if not os.path.exists(venv_path):
    print("Ambiente virtuale non trovato, creazione in corso...")
    # Crea l'ambiente virtuale
    subprocess.check_call([sys.executable, '-m', 'venv', venv_path])

    # Installa i pacchetti necessari
    subprocess.check_call([os.path.join(venv_path, 'bin', 'pip'), 'install', '-r', 'requirements.txt'])

# Attiva l'ambiente virtuale
activate_script = os.path.join(venv_path, 'bin', 'activate_this.py')
exec(open(activate_script).read(), {'__file__': activate_script})

# Da qui in poi il codice continua normalmente


class ConversionTask(QRunnable):
    def __init__(self, image_path, output_folder, worker):
        super().__init__()
        self.image_path = image_path
        self.output_folder = output_folder
        self.worker = worker  # Riferimento al thread principale

    def run(self):  # Assicurati di avere questo metodo correttamente definito
        try:
            img = Image.open(self.image_path)
            img = img.convert("RGBA")
            output_path = os.path.join(self.output_folder, os.path.basename(self.image_path).replace(".jpg", ".webp"))
            img.save(output_path, "WEBP", quality=65)

        except Exception as e:
            print(f"Errore durante la conversione di {self.image_path}: {e}")

        finally:
            # Emetti il segnale di completamento del task
            self.worker.completed_images += 1
            self.worker.progress.emit(self.worker.completed_images, self.worker.total_images)


class WorkerThread(QThread):
    progress = pyqtSignal(int, int)

    def __init__(self, folder, output_folder, max_conversions=4):
        super().__init__()
        self.input_folder = folder
        self.output_folder = output_folder
        self.max_conversions = max_conversions
        self.is_stopped = False  # Flag per indicare se il thread deve essere fermato

        self.total_images = 0
        self.completed_images = 0

        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(self.max_conversions)

    def run(self):
        images = glob.glob(os.path.join(self.input_folder, "*.[jp][pn]g"))
        self.total_images = len(images)

        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        for image_path in images:
            if self.is_stopped:  # Controlla se il thread deve essere fermato
                break
            task = ConversionTask(image_path, self.output_folder, self)
            self.thread_pool.start(task)

        # Attendi il completamento di tutti i task
        self.thread_pool.waitForDone()

    def stop(self):
        self.is_stopped = True
        self.thread_pool.waitForDone()  # Attendi che i task già in esecuzione vengano completati



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Folder Converter to WebP")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()
        self.setCentralWidget(QWidget(self))
        self.centralWidget().setLayout(layout)

        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["", "Nome Cartella", "Convertite", "Total", "Status", "Apri la cartella"])

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(QHeaderView.Fixed)  
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)

        self.table.setColumnWidth(0, 50)  
        self.table.verticalHeader().setVisible(False)

        # Stile globale per le altre colonne (grigio, font normale)
        self.table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: transparent;
                color: #A0A0A0;
                font-weight: normal;
            }
        """)

        # Imposta il titolo della prima colonna (indice 0) in nero e grassetto
        first_header = self.table.horizontalHeaderItem(1)
        if first_header is not None:
            first_header.setForeground(QColor('black'))
            font = QFont()
            font.setBold(True)
            first_header.setFont(font)

        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                alternate-background-color: #f0f0f0;  
            }
            QTableWidget::item {
                background-color: transparent;
                color: #A0A0A0; 
            }
        """)

        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        
        self.add_folder_button = QPushButton("Aggiungi Cartella")
        self.add_folder_button.setStyleSheet("""
            QPushButton {
                background-color: white; 
                color: #007AFF; 
                border-radius: 5px; 
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #007AFF; 
                color: white;
            }
        """)
        self.add_folder_button.setFixedHeight(40)
        self.add_folder_button.clicked.connect(self.add_folder)
        button_layout.addWidget(self.add_folder_button)

        self.close_button = QPushButton("Chiudi")
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: black; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                padding: 10px;
            }
            QPushButton:hover {
                background-color: red;
            }
        """)
        self.close_button.setFixedHeight(40)
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)  

        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            folder = url.toLocalFile()
            if os.path.isdir(folder):
                self.process_folder(folder)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleziona Cartella")
        if folder:
            self.process_folder(folder)

    def process_folder(self, folder):
        output_folder = os.path.join(folder, "convertite")
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        stop_button = QPushButton("X")
        stop_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: gray;
            }
            QPushButton:hover {
                color: red;
            }
        """)
        stop_button.clicked.connect(lambda: self.stop_process(row_position))  
        self.table.setCellWidget(row_position, 0, stop_button)  

        folder_name = Path(folder).name
        folder_widget = QWidget()
        folder_layout = QHBoxLayout()
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel()
        icon_path = "folder_icon.png"
        if os.path.exists(icon_path):
            icon_pixmap = QPixmap(icon_path)
            icon_pixmap = icon_pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(icon_pixmap)
        else:
            icon_label.setText("📁")  # Usa un'emoji come fallback


        folder_label = QLabel(folder_name)  
        folder_label.setStyleSheet("color: black;")

        folder_layout.addWidget(icon_label)
        folder_layout.addWidget(folder_label)
        folder_widget.setLayout(folder_layout)
        
        self.table.setCellWidget(row_position, 1, folder_widget)  

        self.table.setItem(row_position, 2, QTableWidgetItem("0"))  
        self.table.item(row_position, 2).setFlags(Qt.ItemIsEnabled)  
        self.table.item(row_position, 2).setTextAlignment(Qt.AlignCenter) 

        self.table.setItem(row_position, 3, QTableWidgetItem(str(len(glob.glob(os.path.join(folder, "*.[jp][pn]g"))))))  
        self.table.item(row_position, 3).setFlags(Qt.ItemIsEnabled)  
        self.table.item(row_position, 3).setTextAlignment(Qt.AlignCenter)

        progress_widget = QWidget()
        progress_layout = QVBoxLayout()
        progress_layout.setAlignment(Qt.AlignCenter)  
        progress_widget.setLayout(progress_layout)

        progress_bar = QProgressBar(self)
        progress_bar.setAlignment(Qt.AlignCenter)
        progress_bar.setMaximumHeight(20)  
        progress_bar.setTextVisible(False)  
        progress_bar.setStyleSheet("""
            QProgressBar {
                border-radius: 10px; 
                background-color: #e0e0e0; 
            }
            QProgressBar::chunk {
                background-color: #007AFF; 
                border-radius: 10px; 
            }
        """)

        progress_layout.addWidget(progress_bar)  
        self.table.setCellWidget(row_position, 4, progress_widget)  

        open_button = QPushButton("Vedi!")  
        open_button.setStyleSheet("""
            QPushButton {
                background-color: transparent; 
                color: #007AFF; 
                border: 0.5px solid #007AFF; 
                border-radius: 5px; 
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #007AFF; 
                color: white;
            }
        """)
        open_button.clicked.connect(lambda: subprocess.run(["open", output_folder]))  
        self.table.setCellWidget(row_position, 5, open_button)  

        # Collega il segnale di progresso passando il row_position come lambda
        self.worker_thread = WorkerThread(folder, output_folder, max_conversions=4)
        self.worker_thread.progress.connect(lambda completed, total: self.update_progress(row_position, completed, total))
    
        self.worker_thread.finished.connect(lambda: self.add_folder_button.setEnabled(True))  # Riabilita il pulsante al termine
        self.worker_thread.start()

    def stop_process(self, row_position):
        if self.worker_thread.isRunning():
            self.worker_thread.stop()  # Chiamata al metodo stop per interrompere il thread in modo sicuro
            
        for column in range(self.table.columnCount()):
            item = self.table.item(row_position, column)
            if item:
                item.setForeground(Qt.gray)
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)

        progress_widget = self.table.cellWidget(row_position, 4)
        if progress_widget:
            progress_bar = progress_widget.layout().itemAt(0).widget()
            if progress_bar:
                progress_bar.setValue(0)

        self.confirm_remove_row(row_position)


    def update_progress(self, row_position, completed, total):
        progress_widget = self.table.cellWidget(row_position, 4)
        if progress_widget:
            progress_bar = progress_widget.layout().itemAt(0).widget()
            if progress_bar:
                # Aggiorna il valore della progress bar in base al completamento
                percentage = int((completed / total) * 100)
                progress_bar.setValue(percentage)

                # Imposta lo stile blu durante il processo
                progress_bar.setStyleSheet("""
                    QProgressBar {
                        border-radius: 10px; 
                        background-color: #e0e0e0; 
                    }
                    QProgressBar::chunk {
                        background-color: #007AFF;  /* Blu durante il processo */
                        border-radius: 10px; 
                    }
                """)

                self.table.item(row_position, 2).setText(str(completed))  # Aggiorna la colonna "Convertite"

                # Se il completamento è al 100%, cambia il colore in light green
                if completed == total:
                    progress_bar.setStyleSheet("""
                        QProgressBar {
                            border-radius: 10px; 
                            background-color: #e0e0e0; 
                        }
                        QProgressBar::chunk {
                            background-color: lightgreen;  /* Verde chiaro al completamento */
                            border-radius: 10px; 
                        }
                    """)
                    self.table.item(row_position, 2).setText(str(completed))  # Aggiorna la colonna "Convertite" con il totale


    def confirm_remove_row(self, row_position):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setText("Il processo è terminato o interrotto. Vuoi rimuovere la riga?")
        msg.setWindowTitle("Conferma Rimozione")

        icon_path = "icon-pluto.png"  
        icon = QPixmap(icon_path)
        msg.setIconPixmap(icon.scaled(160, 160, Qt.KeepAspectRatio))  
        
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        result = msg.exec_()

        if result == QMessageBox.Yes:
            self.table.removeRow(row_position)

if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
