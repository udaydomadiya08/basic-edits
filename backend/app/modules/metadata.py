import json
import csv
import os

class MetadataManager:
    def __init__(self, output_dir):
        self.output_dir = output_dir

    def save_metadata(self, query, images_info):
        meta_dir = os.path.join(self.output_dir, "metadata")
        os.makedirs(meta_dir, exist_ok=True)
        
        # Save JSON
        json_path = os.path.join(meta_dir, f"{query}.json")
        with open(json_path, 'w') as f:
            json.dump(images_info, f, indent=4)
            
        # Save CSV
        csv_path = os.path.join(meta_dir, f"{query}.csv")
        if images_info:
            keys = images_info[0].keys()
            with open(csv_path, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(images_info)
