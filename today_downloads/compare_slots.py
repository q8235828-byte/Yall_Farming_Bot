import cv2, numpy as np

p = cv2.imread('piece_extracted.png')
s1 = cv2.imread('slot1_extracted.png')
s2 = cv2.imread('slot2_extracted.png')

print("Piece mean:", np.mean(p))
print("Slot 1 mean:", np.mean(s1))
print("Slot 2 mean:", np.mean(s2))
