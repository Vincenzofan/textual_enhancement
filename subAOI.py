#!/usr/bin/env python
# coding: utf-8


from PIL import ImageFont, ImageDraw
import cv2

from functools import partial
import pysubs2
from pysubs2.time import ms_to_frames, ms_to_str, frames_to_ms

import re
import pandas as pd
from math import floor, ceil
import json



class SubAOI:
    
    def __init__(
        self,
        fontname, 
        fontsize_in_px, 
        subtitlepath,
        screensize,
        vertical_offset,
        vertical_offset_top = None,
        base_line = 2,
        target_words = None 
    ):
        self.font = ImageFont.truetype(fontname, fontsize_in_px)
        self.fontsize_in_px = fontsize_in_px
        self.subs = pysubs2.load(subtitlepath)
        self.screen_width, self.screen_height = screensize 
     
        self.base = vertical_offset*self.screen_height
        
        if vertical_offset_top:
            self.base_top = vertical_offset_top*self.screen_height
        self.base_line = base_line
        
        self.target_words = target_words
        
    def __insertRecord(self,
                       target,
                       start_point, 
                       end_point, 
                       start_time, 
                       end_time, 
                       duration, 
                       line_number):
        
        self.targets.append(target)
        self.start_points.append(start_point)
        self.end_points.append(end_point)
        self.start_times.append(start_time)
        self.end_times.append(end_time)
        self.durations.append(duration)
        self.line_numbers.append(line_number)
        
    def __calculateHorizontals(self,
                               line,
                               left, 
                               right):
        length_line = self.font.getlength(line)
        length_left = self.font.getlength(left)
        length_right = self.font.getlength(right)
        half_screen = self.screen_width/2
        
        left_co = round(half_screen - length_line/2 + length_left)
        right_co = round(half_screen + length_line/2 - length_right)
        
        return (left_co, right_co)
    
    def __lineToTokens(self, text):
        
        tokens = text.split(" ")
        targets = []
        
        tmp_lefts = []
        tmp_rights = []
        
        lefts = []
        rights = []

        for i, w in enumerate(tokens):
            try:
                left = " ".join(tokens[:i])
                left = left+" " if i>0 else left
                target = tokens[i]
                right = " ".join(tokens[i+1:])
                right = " "+right if i<len(tokens)-1 else right
                assert len(left)+ len(target)+ len(right) == len(text)
            except(AssertionError):
                raise Exception("Error parsing: "+text)

            left_co, right_co = self.__calculateHorizontals(line=text, left=left, right=right)
            
            targets.append(target)
            tmp_lefts.append(left_co)
            tmp_rights.append(right_co)
            
        # seam the gaps 
        if (len(tokens)>1):

            lefts.append(tmp_lefts[0])

            i = 0
            while i < len(tmp_rights)-1:

                middle = (tmp_rights[i] + tmp_lefts[i+1])/2
                rights.append(floor(middle+0.1))
                lefts.append(ceil(middle+0.1))
                i+=1
                    
            rights.append(tmp_rights[-1])
        else:
            lefts = tmp_lefts
            rights = tmp_rights
            
        return list(zip(targets, lefts, rights))
           
    def calculate(self,
                  whole_line = False,
                  line_spacing = 0,
                  **paddings):
        '''
        padding: (left, top, right, bottom)
    
        '''
        
        self.targets = []
        self.start_points = []
        self.end_points = []
        self.start_times = []
        self.end_times = []
        self.durations = []
        self.line_numbers = []
        
        padding_first_line = paddings.get("first_line")
        padding_second_line = paddings.get("second_line")
        padding_single_line = paddings.get("single_line")
        
        half_width = self.screen_width/2
        
        # AOIs for targets 
        if self.target_words:
            
            for entry in self.target_words:
                
                index, target = entry
                index = index -1 
                line = self.subs[index]
                
                top_line = re.match(r"{\\an8}", line.text)
                top_base_line = self.base_top if top_line else self.base
                text = line.text[6:] if top_line else line.text

                try:
                    match = re.search(target, text.lower()) #case insensitive 
                    target_start, target_end = match.span()
                except:
                    print ("Unable to locate "+
                           str(entry)+
                           " in the specified line. Check spelling and line number")
                    continue

                double_line = re.search(r"\\N", text)

                if (double_line):

                    start, end = double_line.span()
                    first_line, second_line = (text[:start], text[end:])

                    #target in second line
                    if target_start > end:
                        
                        left_part = second_line[:(target_start-end)]
                        right_part = second_line[(target_end-end):]
   
                        left, right = self.__calculateHorizontals(line=second_line,
                                                                 left=left_part,
                                                                 right=right_part)
    
                        if top_line:
                            top = round(top_base_line+self.fontsize_in_px+line_spacing) 
                        else:
                            top = round(top_base_line)
                            
                        bottom = top + self.fontsize_in_px
                        
                        if padding_second_line:
                            left = left-padding_second_line[0]
                            top = top-padding_second_line[1]
                            right = right+padding_second_line[2]
                            bottom = bottom+padding_second_line[3]
                            

                        self.__insertRecord(
                                target = target,
                                start_point = (left, top),
                                end_point = (right, bottom),
                                start_time = line.start,
                                end_time = line.end,
                                duration = line.duration,
                                line_number = index+1
                            )
                    
                    #target in first line
                    else:
                        
                        left_part = first_line[:target_start]
                        right_part = first_line[target_end:]
   
                        left, right = self.__calculateHorizontals(line=first_line,
                                                                 left=left_part,
                                                                 right=right_part)
                        if top_line:
                            top = round(top_base_line)
                        else:
                            top = round(top_base_line-self.fontsize_in_px-line_spacing)
                            
                        bottom = top + self.fontsize_in_px
                        
                        if padding_first_line:
                            left = left-padding_first_line[0]
                            top = top-padding_first_line[1]
                            right = right+padding_first_line[2]
                            bottom = bottom+padding_first_line[3]

                        self.__insertRecord(
                                target = target,
                                start_point = (left, top),
                                end_point = (right, bottom),
                                start_time = line.start,
                                end_time = line.end,
                                duration = line.duration,
                                line_number = index+1
                            )
                else:
                    left_part = text[:target_start]
                    right_part = text[target_end:]
   
                    left, right = self.__calculateHorizontals(line=text,
                                                              left=left_part,
                                                              right=right_part)
                    top = round(top_base_line)
                            
                    bottom = top + self.fontsize_in_px
                
                    if padding_single_line:
                            left = left-padding_single_line[0]
                            top = top-padding_single_line[1]
                            right = right+padding_single_line[2]
                            bottom = bottom+padding_single_line[3]

                    self.__insertRecord(
                            target = target,
                            start_point = (left, top),
                            end_point = (right, bottom),
                            start_time = line.start,
                            end_time = line.end,
                            duration = line.duration,
                            line_number = index+1
                        )
                
        # AOI for whole line 
        elif whole_line:
            
            for index, line in enumerate(self.subs):
            
                top_line = re.match(r"{\\an8}", line.text)

                top_base_line = self.base_top if top_line else self.base
                text = line.text[6:] if top_line else line.text
                
                double_line = re.search(r"\\N", text)

                if (double_line):

                    start, end = double_line.span()
                    first_line = line.text[:start]
                    second_line = line.text[end:]

                    left_first_line = round(half_width - self.font.getlength(first_line)/2)
                    right_first_line = round(half_width + self.font.getlength(first_line)/2)

                    left_second_line = round(half_width - self.font.getlength(second_line)/2)
                    right_second_line = round(half_width + self.font.getlength(second_line)/2)
                    
                    if top_line:
                        top_first_line = round(top_base_line)
                        bottom_first_line = round(top_base_line+self.fontsize_in_px)
                        
                        top_second_line = bottom_first_line+line_spacing
                        bottom_second_line = top_second_line+self.fontsize_in_px
                    else:
                        if self.base_line == 2:
                            top_first_line = round(top_base_line - self.fontsize_in_px-line_spacing)
                            bottom_first_line = round(top_base_line-line_spacing)

                            top_second_line = round(top_base_line)
                            bottom_second_line = round(top_base_line + self.fontsize_in_px)
                            
                    if padding_first_line:
                        left_first_line = left_first_line-padding_first_line[0]
                        top_first_line = top_first_line-padding_first_line[1]
                        right_first_line = right_first_line+padding_first_line[2]
                        bottom_first_line = bottom_first_line+padding_first_line[3]
                        
                    if padding_second_line:
                        left_second_line = left_second_line-padding_first_line[0]
                        top_second_line = top_second_line-padding_first_line[1]
                        right_second_line = right_second_line+padding_first_line[2]
                        bottom_second_line = bottom_second_line+padding_first_line[3]      
                   
                    start_point_first = (left_first_line, top_first_line)
                    start_point_second = (left_second_line, top_second_line)

                    end_point_first = (right_first_line, bottom_first_line)
                    end_point_second = (right_second_line, bottom_second_line)
                    

                    self.__insertRecord(target="line_"+str(index+1)+"_first",
                                        start_point=start_point_first,
                                        end_point=end_point_first,
                                        start_time=line.start,
                                        end_time=line.end,
                                        duration=line.duration,
                                        line_number=index+1
                                       )
                    
                    self.__insertRecord(target="line_"+str(index+1)+"_second",
                                        start_point=start_point_second,
                                        end_point=end_point_second,
                                        start_time=line.start,
                                        end_time=line.end,
                                        duration=line.duration,
                                        line_number=index+1
                                       )
                else:
                    left = round(half_width - self.font.getlength(text)/2)
                    right = round(half_width + self.font.getlength(text)/2)

                    top = round(top_base_line)
                    bottom = round(top + self.fontsize_in_px) 
                    
                    if padding_single_line:
                        left = left-padding_single_line[0]
                        top = top-padding_single_line[1]
                        right = right+padding_single_line[2]
                        bottom = bottom+padding_single_line[3]

                    start_point = (left, top)
                    end_point = (right, bottom)
                    self.__insertRecord(target="line_"+str(index+1),
                                        start_point=start_point,
                                        end_point=end_point,
                                        start_time=line.start,
                                        end_time=line.end,
                                        duration=line.duration,
                                        line_number=index+1)
                    
        # default word by word segmentation          
        else:
            for index, line in enumerate(self.subs):
            
                top_line = re.match(r"{\\an8}", line.text)

                top_base_line = self.base_top if top_line else self.base
                text = line.text[6:] if top_line else line.text
                
                double_line = re.search(r"\\N", text)

                if (double_line):

                    start, end = double_line.span()
                    first_line = text[:start]
                    second_line = text[end:]
                    
                    if top_line:
                        top_first_line = round(top_base_line)
                        bottom_first_line = round(top_base_line+self.fontsize_in_px)
                        
                        top_second_line = bottom_first_line+line_spacing
                        bottom_second_line = top_second_line+self.fontsize_in_px
                    else:
                        if self.base_line == 2:
                            top_first_line = round(top_base_line - self.fontsize_in_px-line_spacing)
                            bottom_first_line = round(top_base_line-line_spacing)

                            top_second_line = round(top_base_line)
                            bottom_second_line = round(top_base_line + self.fontsize_in_px)
                        
                    tokens_first = self.__lineToTokens(first_line)
                    tokens_second = self.__lineToTokens(second_line)
                    
                    if padding_first_line:
                       
                        tokens_first[0] = (tokens_first[0][0], 
                                            tokens_first[0][1]-padding_first_line[0],
                                            tokens_first[0][2])
                        tokens_first[-1] = (tokens_first[-1][0], 
                                            tokens_first[-1][1],
                                            tokens_first[-1][2]+padding_first_line[2])
                   
                    if padding_second_line: 
                        
                        tokens_second[0] = (tokens_second[0][0], 
                                            tokens_second[0][1]-padding_second_line[0],
                                            tokens_second[0][2])
                        tokens_second[-1] = (tokens_second[-1][0], 
                                            tokens_second[-1][1],
                                            tokens_second[-1][2]+padding_second_line[2])
                   
                    for target, left, right in tokens_first:
                        
                        top = top_first_line
                        bottom = bottom_first_line
                        
                        if padding_first_line:
                            top = top-padding_first_line[1]
                            bottom = bottom+padding_first_line[3]
                            
                        self.__insertRecord(target=target + "_@_" +str(index+1),
                                            start_point=(left, top),
                                            end_point=(right, bottom),
                                            start_time=line.start,
                                            end_time=line.end,
                                            duration=line.duration,
                                            line_number=index+1)
                        
                    for target, left, right in tokens_second:
                        top = top_second_line
                        bottom = bottom_second_line
                        
                        if padding_second_line:
                            
                            top = top_second_line-padding_second_line[1]
                            bottom = bottom_second_line+padding_second_line[3]
                            
                        self.__insertRecord(target=target + "_@_" +str(index+1),
                                            start_point=(left, top),
                                            end_point=(right, bottom),
                                            start_time=line.start,
                                            end_time=line.end,
                                            duration=line.duration,
                                            line_number=index+1)

                else:
                        
                    tokens = self.__lineToTokens(text)
                    
                    if padding_single_line:
                       
                        tokens[0] = (tokens[0][0], 
                                    tokens[0][1]-padding_single_line[0],
                                    tokens[0][2])
                        
                        tokens[-1] = (tokens[-1][0], 
                                     tokens[-1][1],
                                     tokens[-1][2]+padding_single_line[2])
                   
                    for target, left, right in tokens:
                        
                        top = round(top_base_line)
                        bottom = round(top + self.fontsize_in_px) 
                        
                        if padding_single_line:
                            
                            top = top-padding_single_line[1]
                            bottom = bottom+padding_single_line[3]
                        
                        self.__insertRecord(target=target + "_@_" +str(index+1),
                                            start_point=(left, top),
                                            end_point=(right, bottom),
                                            start_time=line.start,
                                            end_time=line.end,
                                            duration=line.duration,
                                            line_number=index+1)
        
        d = {"target": self.targets,
             "start_point": self.start_points,
             "end_point": self.end_points,
             "start_time": self.start_times,
             "end_time": self.end_times, 
             "duration": self.durations, 
             "line_number": self.line_numbers}
           
        coordinates = pd.DataFrame(d, columns=["target",
                                               "start_point",
                                               "end_point", 
                                               "start_time",
                                               "end_time", 
                                               "duration", 
                                               "line_number"]) 
        return coordinates
    
    @staticmethod
    def view_line(
        coordinates,
        line_number,
        image,
        color = (0,140,255),
        thickness = 2):
        
        frame = cv2.imread(image)
        
        line = coordinates[coordinates["line_number"] == line_number]
        line
        
        for start_point, end_point in zip(line["start_point"], line["end_point"]):
            cv2.rectangle(frame, start_point, end_point, color, thickness)
        
        cv2.startWindowThread()
        window = "Press any key to exit"
        cv2.imshow(window, frame)

        cv2.waitKey(0) 

        cv2.destroyWindow(window) 
        cv2.waitKey(1) 
                

