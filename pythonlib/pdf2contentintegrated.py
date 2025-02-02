import fitz  # PyMuPDF
import pandas as pd
import re
import numpy as np
from collections import Counter
import csv
import os
import torch
import torchvision
from imgdetocr import objectvisionizer
from imgdetoctretina import retinaobjectvisionizer
import nltk
import cv2
from io import BytesIO
import matplotlib.pyplot as plt
from PIL import Image
import imghdr
from aimodelbuild import aienginmodelbuild

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')
nltk.download('averaged_perceptron_tagger_eng')
nltk.download('wordnet')
nltk.download('punkt_tab')
from TextPreprocessing import text_preprocessing
class pdf2content_integrated:
    def __init__(self,source_pdf_file_path,out_folder,filename,model_path,image_path,confirmeddb_path):
        '''self.model_path = os.path.join(model_path,'objdet.pth')
        self.model = torch.load(self.model_path, torch.device('cpu'))'''
        self.confirmeddb_path=confirmeddb_path
        self.model_path = os.path.join(model_path,'objdetretinanet.pt')
        self.model = torchvision.models.detection.retinanet_resnet50_fpn(num_classes=2, weights=None)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        # Load the trained weights
        self.knowledgedbimage= image_path+"/knowledgegraph"
        self.model.load_state_dict(torch.load(self.model_path, map_location=device))
        self.model.eval()
        self. model.to(device)
        self.image_path=image_path
        if not os.path.exists(self.image_path):
            os.makedirs(self.image_path)
            print(f"Directory '{self.image_path}' created.")
        # Load the trained weights
        self.pdf_file_path = source_pdf_file_path
        print('pdf2content_integrated_test')
        self.out_folder=out_folder
        self.filename=filename
        self.output_filename = f"{self.out_folder}/{self.filename}"
        #self.pdf_file_path = "/Users/sauravsahu/Downloads/Automated_2013-nissan-leaf-27_194.pdf"  # Provide the path to your PDF file
        data = self.extract_text_with_style(self.pdf_file_path)
        #print(data.shape)
        data = data.dropna(subset=['Text'])
        data = data[data['Text'] != '']
        df_exploded = data.explode('cc_segment_image')
        #print('df_exploded',df_exploded.columns)
        obj_aiextract = aienginmodelbuild(df_exploded,self.knowledgedbimage)
        aiengineerextract = obj_aiextract.datapreparation()
        #print('aiengineerextract',aiengineerextract.columns)
        main_component = aiengineerextract['Header_image'].unique().tolist()
        sub_component = aiengineerextract['Text'].unique().tolist()

        main_component_file = os.path.join(self.confirmeddb_path, "main_component.txt")
        sub_component_file = os.path.join(self.confirmeddb_path, "sub_component.txt")

        os.remove(main_component_file)
        os.remove(sub_component_file)
        print('main_component_file',main_component_file)
        print('sub_component_file',sub_component_file)
        
        main_component_tuple = tuple(main_component)

        sub_component_tuple = tuple(sub_component)
        
    
        with open(main_component_file, "a") as f:
            f.write("\n".join(main_component_tuple) + "\n")
            f.close()

        
        with open(sub_component_file, "a") as f:
            f.write("\n".join(sub_component_tuple) + "\n")
            f.close()

        #aiengineerextract=pd.DataFrame(aiengineerextract_df[0])
        self.save_output(df_exploded,self.out_folder,self.filename+'_knowledge_db_data.csv')
        self.save_output(aiengineerextract,self.confirmeddb_path,self.filename+'_kdb_data.csv')


    def extract_text_with_style(self,pdf_file):
        df_data = []
        doc = fitz.open(pdf_file)
        text_with_style = []
        pg_number = 0
        for page in doc:
            blocks = page.get_text("dict", sort=True)["blocks"]
            for block in blocks:
                number = block['number']
                type_ = block['type']
                bbox = block['bbox']
                lines = block.get('lines', [])
                for line in lines:
                    spans = line['spans']
                    for span in spans:
                        size = span['size']
                        font = span['font']
                        color = span['color']
                        text = span['text']
                        origin = span['origin']
                        span_bbox = span['bbox']
                        df_data.append([pg_number, number, type_, bbox, text, size, font, color, origin, span_bbox, None, None, None, None, None, None, None, None, None])
                width = block.get('width', None)
                height = block.get('height', None)
                ext = block.get('ext', None)
                colorspace = block.get('colorspace', None)
                xres = block.get('xres', None)
                yres = block.get('yres', None)
                bpc = block.get('bpc', None)
                transform = block.get('transform', None)
                size = block.get('size', None)
                image = block.get('image', None)
                df_data.append([pg_number, number, type_, bbox, None, None, None, None, None, None, width, height, ext, colorspace, xres, yres, bpc, transform, size, image])
            pg_number += 1
        df = pd.DataFrame(df_data, columns=['pg_number', 'Number', 'Type', 'Bbox', 'Text', 'Size', 'Font', 'Color', 'Origin', 'Span_Bbox', 'Width', 'Height', 'Ext', 'Colorspace', 'Xres', 'Yres', 'Bpc', 'Transform', 'Size', 'Image'])
        data_df_prep = self.dataprep(df)
        print('data_df_prep',data_df_prep.head())
        data_df = self.buildhierarchy(data_df_prep)
        return data_df

    def order_numerical_column_desc_start_one(self,df, column_name):
        unique_values = sorted(df[column_name].unique(), reverse=True)
        value_to_index = {value: index + 1 for index, value in enumerate(unique_values)}
        ordered_data = df[column_name].map(lambda x: value_to_index[x])
        return ordered_data

    def is_not_proper_word(self,word):
        if word == "None" or word is None or pd.isna(word) or len(word.lstrip().rstrip()) == 1:
            return True
        word = re.sub(r'[^a-zA-Z0-9]', '', word)
        return not bool(re.match(r'^[a-zA-Z]+$', word))

    def expand_list_column(self,df, column_name, new_column_names):
        new_columns_df = df.apply(lambda row: pd.Series(row[column_name], index=new_column_names), axis=1)
        return pd.concat([df, new_columns_df], axis=1)


    def extract_columns(self,df_expanded_span, df1_columns):
        data_dict = {}
        for col in df1_columns:
            try:
                column_data = df_expanded_span[col].iloc[:, 0] if len(df_expanded_span[col].shape) == 2 else df_expanded_span[col]
                data_dict[col] = column_data
            except KeyError:
                print(f"Column '{col}' not found in df_expanded_span.")
        extracted_df = pd.DataFrame(data_dict)
        return extracted_df
    '''
    def buildhierarchy(self,data_df):
        max_value = data_df['Header_style'].max()
        for i in range(0, max_value + 1):            
            data_df[f'Header_{i}'] = ''
        old_number_mod = 1
        para_style_number = 0 
        para_style_name = ''
        old_number=1
        headers_df = []
        for index, row in data_df.iterrows():
            para_style_number = row['Header_style']
            para_style_name = 'Header_'+str(para_style_number)
            if para_style_number < max_value:
                if para_style_number==1:
                    headers_df=[]
                    headers_df.append(row['Text'].strip().replace(":", "").lower())
                if para_style_number == old_number_mod:
                    headers_df.pop()
                    headers_df.append(row['Text'].strip().replace(":", "").lower())
                if para_style_number > old_number_mod:
                    difference = para_style_number - old_number_mod
                    if difference > 1:
                        headers_df.append(row['Text'].strip().replace(":", "").lower())
                    #print('old_number_mod, para_style_number, len(headers_df), headers_df',old_number_mod, para_style_number, len(headers_df), headers_df)
                if para_style_number < old_number_mod:
                    difference = old_number_mod - para_style_number
                    for i in range(para_style_number,old_number_mod+1):
                        if len(headers_df) != 0:
                            headers_df.pop()
                    headers_df.append(row['Text'].strip().replace(":", "").lower())
                for i in range(0,len(headers_df)):
                    data_df.at[index,'Header_'+str(i)] = headers_df[i]
                old_number_mod = para_style_number
            else: 
                #print(para_style_name,len(headers_df))
                for i in range(0,len(headers_df)):
                    data_df.at[index,'Header_'+str(i)] = headers_df[i]
            old_number = para_style_number
        return data_df
    '''
    def buildhierarchy(self,data_df):
        max_value = data_df['Header_style'].max()
        ##print('buildhierarchy begins line 195')
        headers_df = []
        old_number_mod = 1
        old_number = 1
        prev_header_image = ""
        for index, row in data_df.iterrows():
            #print('buildhierarchy for loop begins line 201')
            if row['Header_image'] != None and row['Header_image'] >1:
                data_df.at[index, 'Header_image'] = row['Text']
                prev_header_image = row['Text']
            elif row['Header_image'] != None and row['Header_image'] ==0:
                data_df.at[index, 'Header_image'] = row['Text']
            elif row['Text'] == 'Main Image':
                data_df.at[index, 'Header_image'] = row['Text'] +" - "+row['image_name']
            elif row['ocr_det_arr'] != None:
                data_df.at[index, 'Header_image'] = prev_header_image

            para_style_number = row['Header_style']
            para_style_name = 'Header_' + str(para_style_number)
            #print('buildhierarchy para_style_name begins line 214')
            if para_style_number < max_value:
                #print('buildhierarchy para_style_number: begins line 216')
                if para_style_number == 1:
                    headers_df = [row['Text'].replace(":", "").lower()]
                    #print('buildhierarchy para_style_number: begins line 219')
                elif para_style_number == old_number_mod:
                    #print('buildhierarchy para_style_number: begins line 221')
                    headers_df.pop()
                    headers_df.append(row['Text'].strip().replace(":", "").lower())
                elif para_style_number > old_number_mod:
                    #print('buildhierarchy para_style_number: begins line 225')
                    difference = para_style_number - old_number_mod
                    headers_df.append(row['Text'].strip().replace(":", "").lower())
                elif para_style_number < old_number_mod:
                    #print('buildhierarchy para_style_number: begins line 229')
                    difference = old_number_mod - para_style_number
                    for i in range(difference):
                        headers_df.pop()
                    headers_df.append(row['Text'].strip().replace(":", "").lower())
                
                for i, header in enumerate(headers_df):
                    #print('buildhierarchy for i, header in enumerate(headers_df): begins line 236')
                    data_df.at[index, f'Header_{i}'] = header

                old_number_mod = para_style_number
            else:
                #print('buildhierarchy for i, header in enumerate(headers_df): begins line 241')
                for i, header in enumerate(headers_df):
                    #print('buildhierarchy for i, header in enumerate(headers_df): begins line 243')
                    data_df.at[index, f'Header_{i}'] = header

            old_number = para_style_number
        return data_df
        
    def save_output(self,data, output_folder, filename):
        # Create the subfolder if it doesn't exist
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        # Construct the full path to save the file
        filepath = os.path.join(output_folder, filename)

        # Save the DataFrame to CSV
        data.to_csv(filepath, sep=',', index=False, quotechar='"', quoting=csv.QUOTE_ALL)
        print(f"File saved successfully at {filepath}")
    def bytes_to_image(self,byte_data):
        try:
            img = plt.imread(BytesIO(byte_data))
            return img
        except Exception as e:
            print(f"Error processing image: {e}")
            return None
        
    def dataprep(self,data_df):
        data_df['ocr_det_arr']=None
        data_df['Header_image']=None
        data_df['segment_dictionary']=None
        data_df['cc_segment_image']=None

        segment_dictionary= dict()
        data_df['Bbox'] = data_df.apply(lambda row: row['Span_Bbox'] if pd.isna(row['Width']) or row['Width'] == '' else row['Bbox'], axis=1)
        new_column_names = ['x0', 'y0', 'x1', 'y1']
        df_expanded = self.expand_list_column(data_df, 'Bbox', new_column_names)
        
        df1_columns = ['pg_number', 'Number', 'Type', 'Bbox', 'Text', 'Size', 'Font', 'Color', 'Origin', 'Span_Bbox', 'x0', 'y0', 'x1', 'y1','ocr_det_arr','Header_image','segment_dictionary','cc_segment_image']
        df2_columns = ['pg_number', 'Number', 'Type', 'Bbox', 'Span_Bbox', 'Width', 'Height', 'Ext', 'Colorspace', 'Xres', 'Yres', 'Bpc', 'Transform', 'Size', 'Image', 'x0', 'y0', 'x1', 'y1','ocr_det_arr','Header_image','segment_dictionary','cc_segment_image']
        df1 = self.extract_columns(df_expanded, df1_columns)
        df1 = df1[df_expanded['Text'].notna()]
        df1['image_name'] = np.NaN
        df1['Text'] = df1['Text'].apply(text_preprocessing)
        df1['Text']  = df1['Text'] .apply(lambda x: ' '.join(x))
        df2 = self.extract_columns(df_expanded, df2_columns)
        df2 = df2[(df2['Image']!='') & (df2['Image']!='None') & (df2['Image']!=None ) & (df2['Image'].notna())]
        df2['image_name'] = 'img_'+df2['pg_number'].astype(str)+'_'+df2['Number'].astype(str)+'.'+df2['Ext']
        #self.save_output(df2,"./knowledge_graph_files",'knowledge_graph_image.csv')
        new_row_df = pd.DataFrame(columns=df1.columns)
        for index, row in df2.iterrows():
            cc_segment_key= None
            cc_segment_value= None
            if row['image_name'] is not None:
                output_file_path = os.path.join(self.image_path, f"{row['image_name']}")
                with open(output_file_path, "wb") as f:
                    f.write(row['Image'])
                print(f"Image saved successfully as '{output_file_path}'.")
            else:
                print("No valid image data found in the DataFrame.")

            obj = retinaobjectvisionizer(self.model,row['Image'],row['image_name'],self.image_path)
            ocr_det_arr = np.array(obj.preprocess_image())
            print('Step pdf2contentintegrated_ocr_det_arr',ocr_det_arr, len(ocr_det_arr))
            if len(ocr_det_arr) >1:
                obj_seg = retinaobjectvisionizer(self.model,row['Image'],row['image_name'],self.image_path)
                segment_dictionary = obj_seg.segment_main_image()
                df2.at[index, 'segment_dictionary'] = segment_dictionary
                print('pdf2content - segment_dictionary',segment_dictionary)
            elif len(ocr_det_arr) == 1:
                print('write into cc_segment_value',ocr_det_arr)
                cc_segment_key= ocr_det_arr[0]
                cc_segment_value= segment_dictionary.get(cc_segment_key, None)
            df2.at[index, 'ocr_det_arr'] = ocr_det_arr
            df2.at[index, 'Header_image'] = len(ocr_det_arr)
            print('row[image_name]',row['image_name'],ocr_det_arr,len(ocr_det_arr))
            filtered_df1 = df1[(df1['pg_number'] == row['pg_number']) & (df1['y0'] <= row['y0']) & (df1['y1'] >= row['y0']) & (df1['x0'] >= row['x0']) & (df1['image_name'].isna())]
            filtered_df1 = filtered_df1.copy()
            filtered_df1['diff_x0'] = abs(filtered_df1['x0'] - row['x0'])
            if filtered_df1.empty:
                filtered_df1 = df1[(df1['pg_number'] == row['pg_number']) & (df1['y0'] >= row['y0']) & (df1['y0'] <= row['y1']) & (df1['x0'] >= row['x0']) & (df1['image_name'].isna())]
                filtered_df1 = filtered_df1.copy()
                filtered_df1['diff_x0'] = abs(filtered_df1['x0'] - row['x0'])
                
            #filtered_df1 = pd.concat([filtered_df1, filtered_df2], ignore_index=True).reset_index()
            '''
            print('filtered_df1 columns',filtered_df1.columns)
            print('filtered_df1 shape',filtered_df1.shape)
            print('filtered_df1 head',filtered_df1.head())'''
            
            if filtered_df1.empty:
                new_row_df = pd.DataFrame([row], columns=df1.columns).reset_index(drop=True)
                df1 = pd.concat([df1, new_row_df], ignore_index=True)
            else:
                smallest_row_index = filtered_df1['diff_x0'].idxmin()
                if not filtered_df1.loc[smallest_row_index].empty:
                    df1.loc[smallest_row_index ,'image_name'] = row['image_name']
                    df1.loc[smallest_row_index ,'cc_segment_image'] = row['image_name']
                    #print('row[image_name]',row['image_name'],ocr_det_arr)
                    df1.at[smallest_row_index, 'ocr_det_arr'] = ocr_det_arr
                    df1.at[smallest_row_index, 'Header_image'] = len(ocr_det_arr)
                    df1.at[smallest_row_index, 'segment_dictionary'] = segment_dictionary
                    print('# Check if cc_segment_value is not None, has length >= 1, and does not contain any NaN values')

                    if isinstance(cc_segment_value, list):
                        # Perform the operation on the DataFrame
                        df1.at[smallest_row_index, 'cc_segment_image'] = cc_segment_value
                    #df1.loc[smallest_row_index ,'ocr_det_arr'] = ocr_det_arr

                else:
                    new_row_df = pd.DataFrame([row], columns=df1.columns).reset_index(drop=True)
                    df1 = pd.concat([df1, new_row_df], ignore_index=True)
        
        self.save_output(df2,self.out_folder,self.filename+'_knowledge_db_image.csv')
    
        df1['Text'].fillna(value='Main Image', inplace=True) 
        df1['Size'].fillna(value=0, inplace=True) 
        df1['Font'].fillna(value='', inplace=True) 
        df1['Color'].fillna(value=0, inplace=True) 
        df1['Origin'].fillna(value='', inplace=True) 
        df1['Span_Bbox'].fillna(value='', inplace=True) 
        #df1['Header_image'] = df1.apply(lambda row: row['Text'] if row['Header_image'] is not None and row['Header_image'] > 1 else np.nan, axis=1)

        df1 = df1[(df1['y1'] <= 780) & (df1['y1'] >= 51)]
   
        filtered_indices = df1[df1.apply(lambda row: (pd.isna(row['image_name'])) and len(str(row['Text']).split()) == 1 and self.is_not_proper_word(str(row['Text'])), axis=1)].index

        data_df = df1.drop(filtered_indices)

        data_df['font_size_diff'] = data_df['Size'] - data_df['Size'].value_counts().idxmax()

        data_df['font_size_diff'] = data_df['font_size_diff'].apply(lambda x: 0 if x < 0 else x)

        data_df['Header_style'] = self.order_numerical_column_desc_start_one(data_df, 'font_size_diff')

        return data_df
'''
if __name__ == "__main__":
    pdf_file_path = "/Users/sauravsahu/Downloads/Automated_2013-nissan-leaf-27_194.pdf"  # Provide the path to your PDF file
    data = extract_text_with_style(pdf_file_path)
    print(data.shape)
    save_output(data,"./knowledge_graph_files",'knowledge_graph_text.csv')
'''