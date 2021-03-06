import cv2
import sys
from matplotlib.pyplot import pie
from numpy.lib.function_base import average
import scipy
import numpy as np
import math
import json

from detect_pieces import detect_pieces, image_preprocess, removeShadow

tor = 30

class PuzzleSolver():
    def __init__( self, ori, img, name="test"):
        self.name = name
        self.camera_img = image_preprocess(img)
        # self.camera_img = img
        self.original = removeShadow(ori)
        self.pieces = []
        self.w = 0
        self.h = 0
        self.match = np.zeros([4, 3])

    def detect_pieces(self):
        imgs = self.camera_img
        pieces, mid_points, corners, crops, angles, edges = detect_pieces(imgs, self.name)
        ws = []
        hs = []
        for i in range(len(pieces)):
            self.pieces.append(Puzzle(pieces[i], mid_points[i], corners[i], crops[i], angles[i], edges[i]))
            # print(self.pieces[i].inner.shape)
            tmp_w = max(self.pieces[i].inner.shape[0], self.pieces[i].inner.shape[1])
            tmp_h = min(self.pieces[i].inner.shape[0], self.pieces[i].inner.shape[1])
            ws.append(tmp_w)
            hs.append(tmp_h)
        self.w = average(ws)
        self.h = average(hs)
        self.original = cv2.resize(self.original, (int(self.h*3), int(self.w*4)), interpolation=cv2.INTER_CUBIC)
        cv2.imwrite("./results/" + self.name + '/resize.png', self.original)

    def solve(self, methodId=1):
        methods = ['cv2.TM_CCOEFF', 'cv2.TM_CCOEFF_NORMED', 'cv2.TM_CCORR', 'cv2.TM_CCORR_NORMED', 'cv2.TM_SQDIFF', 'cv2.TM_SQDIFF_NORMED']
        display = self.original.copy()
        middles = []
        for i in range(len(self.pieces)): middles.append(1)
        unmatch_list = []

        for idx, piece in enumerate(self.pieces):
            # if idx != 3: continue
            # gray = cv2.cvtColor(piece.inner, cv2.COLOR_BGR2GRAY)
            # # gray = getRect(gray, piece.corner)
            # ori_gray = cv2.cvtColor(self.original, cv2.COLOR_BGR2GRAY)

            # gray = cv2.cvtColor(piece.inner, cv2.COLOR_BGR2HSV)
            # gray = getRect(gray, piece.corner)
            # ori_gray = cv2.cvtColor(self.original, cv2.COLOR_BGR2HSV)
            gray = piece.inner
            ori_gray = self.original

            w = gray.shape[0]
            h = gray.shape[1]
            ref_w = ori_gray.shape[0]//4
            ref_h = ori_gray.shape[1]//3
            score = -1
            phi_idx = -1
            topleft_idx = -1
            match = False

            rot = gray.copy()
            if abs(gray.shape[0]-gray.shape[1]) > 3:
                phi_candidates = [0, 180] if gray.shape[0]>gray.shape[1] else [90, 270]
            else:
                phi_candidates = [0, 90, 180, 270]
            for phi in phi_candidates:
                rot = scipy.ndimage.rotate(gray, phi)

                method = eval(methods[methodId])

                # Apply template Matching
                res = cv2.matchTemplate(ori_gray, rot, method)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                # If the method is TM_SQDIFF or TM_SQDIFF_NORMED, take minimum
                if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                    top_left = min_loc
                else:
                    top_left = max_loc
                
                if max_val > score:
                    if (top_left[0]%ref_h<tor or (ref_h - top_left[0]%ref_h)<tor) and (top_left[1]%ref_w<tor or (ref_w-top_left[1]%ref_w)<tor):
                        score = max_val
                        phi_idx = phi
                        topleft_idx = top_left
                        match = True
            if match:
                if phi_idx==90 or phi_idx==270:
                    tmp = w
                    w = h
                    h = tmp
                piece.rotEdge(phi_idx)
                top_left = topleft_idx
                bottom_right = (top_left[0] + h, top_left[1] + w)
                cv2.rectangle(display, top_left, bottom_right, (255, 0, 0), 2)
                mid = (int(top_left[0] + h/2), int(top_left[1] + w/2))
                cv2.circle(display, mid, 1, 255, 1)
                cv2.putText(display, f"{idx}", mid, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2, cv2.LINE_AA)
                # print("\nsaving result at ./results/" + self.name + "/matched.jpg")

                # piece.orientation = phi_idx + piece.orientation
                piece.orientation = -phi_idx + piece.orientation
                middles[idx] = [int(top_left[1] + w/2), int(top_left[0] + h/2)]
            else:
                middles[idx] = [0, 0] 
                unmatch_list.append(idx)

        cv2.imwrite("./results/" + self.name + '/matched.jpg', display)
        order = np.argsort(middles, axis=0)
        new = []
        for i in range(len(self.pieces)): new.append([0,0])

        for i in range(len(order)):
            new[order[i][0]][0] = i
            new[order[i][1]][1] = i

        for idx, piece in enumerate(self.pieces):  
            piece.target = [math.floor((new[idx][0])/3), math.floor((new[idx][1])/4)]
            print(f'angle: {piece.orientation:4.3f}\ttarget: {piece.target}\tedge: {piece.edge}')
        
    def save_result(self, path):
        info = dict()
        for idx, p in enumerate(self.pieces):
            info[idx] = {
				"posx":  int(p.pos[0]), 
				"posy":  int(p.pos[1]), 
				"orientation": p.orientation, 
				"targetx": int(p.target[0]*self.h+self.h/2), 
                "targety": int(p.target[1]*self.w+self.w/2)
			}
        with open(path, 'w') as f:
            json.dump(info, f)

class Puzzle():
    def __init__(self, piece, mid, corner, inner, angle, edge):
        self.img = piece
        self.orientation = angle
        self.pos = mid        # current position (from image) 
        self.target = [0,0]        # target position (row, column)
        self.corner = corner
        self.inner = inner
        self.edge = edge
    
    def rotEdge(self, phi_idx):
        n = phi_idx//90
        self.edge = self.edge[n:] + self.edge[:n]

