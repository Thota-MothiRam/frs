import os
import shutil
# from processor.logger import trace, exc


class FolderView:
    def __init__(self, folder_path):
        self.folder_path = folder_path

    def createfolder(self):
        try:
            if not os.path.exists(self.folder_path):
                os.makedirs(self.folder_path)
        except Exception as ex:
            print(f"Failed to create directory {self.folder_path}. Error: {ex}")

    def removefolder(self):
        try:
            if os.path.exists(self.folder_path):
                shutil.rmtree(self.folder_path, ignore_errors=True)
        except Exception as ex:
            print(f"Failed to remove directory {self.folder_path}. Error: {ex}")

    def checkdrive(self):
        try:
            check_drive = str(os.path.exists(self.folder_path.upper() + ':\\'))
        except Exception as ex:
            print(f"Failed to check directory {self.folder_path}. Error: {ex}")
