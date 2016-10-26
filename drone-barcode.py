#
# Barcode detection from video stream using OpenCV2
#

import argparse
import cv2
import numpy as np


MAIN_WND_NAME = 'POI'
WND_BIG_NAME = 'Result'
t0 = cv2.getTickCount()
SHOW_BIG = False
STEP_MODE = 0
DEBUG_MODE = False


def show_scaled(image, image_w=800, image_h=600, title="Image preview"):
    """Scale image buffer to desired dimensions
    """
    imscaled = cv2.resize(image, (image_w, image_h))
    cv2.imshow(title, imscaled)
    char = cv2.waitKey(0)
    cv2.destroyWindow(title)


def log_step(dst, name, data):
    global t0
    t = (cv2.getTickCount() - t0) / cv2.getTickFrequency()
    #log('\tStep <{name}>\t({t0} seconds)'.format(name=name, t0=t))
    dst.append((name, data, t))
    t0 = cv2.getTickCount()


def find_poi(img, thresh_l, thresh_h, blur_x, blur_y, rect_w, rect_h, tx=81, ty=3):
    """Find point of interest (barcode region in image)
    """
    #constants:
    KSIZE = -1
    # ERODE_ITER = 4
    # DILATE_ITER = 4
    THRESH_AMMOUNT = (thresh_l, thresh_h)
    BLUR_AMMOUNT = (blur_x, blur_y)
    RECT = (rect_w, rect_h)
    #<--constants

    global t0
    steps = []

    def _u(x):
        return int(img.shape[0] / (x * 100))

    t0 = cv2.getTickCount()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    log_step(steps, 'gray', cv2.cvtColor(gray.copy(), cv2.COLOR_GRAY2BGR))

    grad_x = cv2.Sobel(gray, ddepth=cv2.cv.CV_32F, dx=1, dy=0, ksize=KSIZE)
    #grad_x = cv2.blur(grad_x, (blur_x, 1))
    log_step(steps, 'grad_x', cv2.cvtColor(grad_x.copy(), cv2.COLOR_GRAY2BGR))

    grad_y = cv2.Sobel(gray, ddepth=cv2.cv.CV_32F, dx=0, dy=1, ksize=KSIZE)
    grad_y = cv2.blur(grad_y, (1, blur_y))
    log_step(steps, 'grad_y', cv2.cvtColor(grad_y.copy(), cv2.COLOR_GRAY2BGR))

    grad = cv2.subtract(grad_x, grad_y)
    log_step(steps, 'grad_sub', cv2.cvtColor(grad.copy(), cv2.COLOR_GRAY2BGR))

    grad = cv2.convertScaleAbs(grad)
    log_step(steps, 'grad', cv2.cvtColor(grad.copy(), cv2.COLOR_GRAY2BGR))

    blurred = cv2.blur(grad, BLUR_AMMOUNT)
    #blurred = grad.copy()
    log_step(steps, 'blur', cv2.cvtColor(blurred.copy(), cv2.COLOR_GRAY2BGR))

    (_, thresh) = cv2.threshold(blurred, THRESH_AMMOUNT[0], THRESH_AMMOUNT[1], cv2.THRESH_BINARY)
    log_step(steps, 'thresh', cv2.cvtColor(thresh.copy(), cv2.COLOR_GRAY2BGR))

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, RECT)
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    closed = cv2.dilate(closed, 4)
    log_step(steps, 'closed', cv2.cvtColor(closed.copy(), cv2.COLOR_GRAY2BGR))

    imopen = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
    kernel = np.ones((5, 5), np.uint8)

    log_step(steps, 'open', cv2.cvtColor(imopen.copy(), cv2.COLOR_GRAY2BGR))

    imout = cv2.bitwise_and(img, img, mask=imopen)
    log_step(steps, 'masked', imout)

    out = imout.copy()
    ret = {'steps': steps, 'result': out}
    return ret


def find_rects(img):
    #log("Looking for rects. Image shape: {}".format(img.shape))
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    conts, hier = cv2.findContours(img_gray.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    if len(conts):
        rect = cv2.minAreaRect(conts[0])
        box = cv2.cv.BoxPoints(rect)
        box = np.int0(box)
        log("Found contours. Shape: {} \n{}".format(conts[0].shape, box), True)
        return box
    else:
        return None


def atlas(imgs, captions, times,  w, h):
    """Glue images together into atlas
    """
    fnt = cv2.FONT_HERSHEY_COMPLEX_SMALL
    iw = w
    ih = h
    xc = 4
    atlas_width  = xc * iw + iw
    atlas_height = (len(imgs) // xc) * ih + ih
    atl = np.zeros((atlas_height, atlas_width, 3), np.uint8)

    for i, img in enumerate(imgs):
        x = (i % xc) * iw
        y = (i // xc) * ih
        xw = x + iw
        yh = y + ih
        atl[y:yh, x:xw] = cv2.resize(img, (iw, ih))
        cv2.putText(atl, "{}: {}".format(captions[i], times[i]), (x + 15, y + 15), fnt, 0.7, (0, 0, 0), 3)
        cv2.putText(atl, "{}: {}".format(captions[i], times[i]), (x + 15, y + 15), fnt, 0.7, (255, 255, 255), 1)

    return atl


def log(x, force=0):
    if DEBUG_MODE or force:
        print x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--img", required=True,  dest='img', help="input image file")
    ap.add_argument("-o", "--out", required=False,  dest='out', help="output image filename")
    args = ap.parse_args()

    global STEP_MODE
    global DEBUG_MODE
    global SHOW_BIG
    global MAIN_WND_NAME
    global WND_BIG_NAME

    # Interface control names
    trk_blur     = 'Blur'
    trk_test     = 'Thresh mean'
    trk_test2    = 'Thresh mean 2'
    trk_thresh_l  = 'ThreshL'
    trk_thresh_h  = 'ThreshH'
    trk_rect_w    = 'RectW'
    trk_rect_h    = 'RectH'

    def nothing(x):
        pass

    cv2.namedWindow(MAIN_WND_NAME)
    cv2.createTrackbar(trk_blur,     MAIN_WND_NAME,  70, 200,  nothing)
    cv2.createTrackbar(trk_test,     MAIN_WND_NAME,  80, 255,  nothing)
    cv2.createTrackbar(trk_test2,    MAIN_WND_NAME,   3, 255,  nothing)
    cv2.createTrackbar(trk_thresh_l, MAIN_WND_NAME, 130, 254,  nothing)
    cv2.createTrackbar(trk_thresh_h, MAIN_WND_NAME, 255, 255,  nothing)
    cv2.createTrackbar(trk_rect_w,   MAIN_WND_NAME, 140, 500,  nothing)
    cv2.createTrackbar(trk_rect_h,   MAIN_WND_NAME,   5, 200,  nothing)

    if args.img == 'cam':
        cap = cv2.VideoCapture(0)
        ret = cap.set(3, 1280)
        ret = cap.set(4, 720)

        log("Capturing from camera...")

        # Handle keyboard input
        while True:
            k = cv2.waitKey(abs(STEP_MODE - 1)) & 0xFF

            if k == ord('s'):
                STEP_MODE = abs(STEP_MODE - 1)
                log("\tStep Mode <{}>".format("ON" if STEP_MODE else "OFF"), 1)

            if k == ord('b'):
                SHOW_BIG = not SHOW_BIG
                log("\tBig view Mode <{}>".format("ON" if SHOW_BIG else "OFF"), 1)
                if not SHOW_BIG:
                    cv2.destroyWindow('big')

            if k == ord('d'):
                DEBUG_MODE = not DEBUG_MODE
                log("\tDebug Mode <{}>".format("ON" if DEBUG_MODE else "OFF"), 1)

            if k == ord('q'):
                log("Exiting")
                break

            ret, frame = cap.read()
            img_orig = frame.copy()
            thresh_l, thresh_h = (cv2.getTrackbarPos(trk_thresh_l, MAIN_WND_NAME),
                                cv2.getTrackbarPos(trk_thresh_h, MAIN_WND_NAME))
            blur_x, blur_y = [cv2.getTrackbarPos(trk_blur, MAIN_WND_NAME)] * 2
            rect_w, rect_h = (cv2.getTrackbarPos(trk_rect_w, MAIN_WND_NAME),
                            cv2.getTrackbarPos(trk_rect_h, MAIN_WND_NAME))
            tx = cv2.getTrackbarPos(trk_test, MAIN_WND_NAME)
            ty = cv2.getTrackbarPos(trk_test2, MAIN_WND_NAME)

            poi = find_poi(frame, thresh_l, thresh_h, blur_x, blur_y, rect_w, rect_h, tx=tx, ty=ty)
            imm = img_orig.copy()
            ims    = []  # image list
            titles = []  # image titles
            times  = []

            for s in poi['steps']:
                titles.append(s[0])
                ims.append(s[1])
                times.append(s[2])

            bbox = find_rects(ims[-1])
            if bbox is not None:
                #log("Drawing a bounding box: {bbox}".format(bbox=bbox), 1)
                cv2.drawContours(imm, [bbox], -1, (0, 255, 0), 5)

                titles.append('POIS')
                ims.append(imm)
                times.append(0)

            atl = atlas(ims, titles, times, 250, 200)
            cv2.imshow(MAIN_WND_NAME + '_tiles', atl)
            if SHOW_BIG:
                cv2.imshow(WND_BIG_NAME, cv2.resize(imm, (1280//3, 720//3)))

        cap.release()
        cv2.destroyAllWindows()

    else:
        # img = None
        print "Loading '{}'".format(args.img)

        if img is not None:
            img = cv2.imread(args.img)
            if img.shape[0] == 0:
                print "Image loading error"
                exit()
        else:
            print "Image loading error"
            exit()

        print "Searching POIs..."
        pois = find_poi(img)
        show_scaled(pois)
        cv2.imwrite(args.out, pois)
        print "Finished"


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
