;;; PCAP Diamond Electrode Generator
;;; Generic mutual-capacitance electrode geometry for early-layout use.
;;; It is not a fabrication-ready touch-panel design or electrical simulation.

(vl-load-com)

(defun pcap:ensure-layer (name color /)
  (if (not (tblsearch "LAYER" name))
    (entmake
      (list
        '(0 . "LAYER")
        '(100 . "AcDbSymbolTableRecord")
        '(100 . "AcDbLayerTableRecord")
        (cons 2 name)
        '(70 . 0)
        (cons 62 color)
        '(6 . "CONTINUOUS"))))
  name)

(defun pcap:closed-polyline (points layer / data)
  (setq data
    (list
      '(0 . "LWPOLYLINE")
      '(100 . "AcDbEntity")
      (cons 8 layer)
      '(100 . "AcDbPolyline")
      (cons 90 (length points))
      '(70 . 1)))
  (foreach point points
    (setq data (append data (list (cons 10 point)))))
  (entmake data))

(defun pcap:block-key (half-x half-y / raw)
  (setq raw (strcat "DSD_" (rtos half-x 2 4) "_" (rtos half-y 2 4)))
  (vl-string-translate ".-" "pm" raw))

(defun pcap:ensure-diamond-block (half-x half-y / name)
  (setq name (pcap:block-key half-x half-y))
  (if (not (tblsearch "BLOCK" name))
    (progn
      (entmake
        (list
          '(0 . "BLOCK")
          '(100 . "AcDbEntity")
          '(8 . "0")
          '(100 . "AcDbBlockBegin")
          (cons 2 name)
          '(70 . 2)
          '(10 0.0 0.0 0.0)))
      (pcap:closed-polyline
        (list
          (list 0.0 half-y)
          (list half-x 0.0)
          (list 0.0 (- half-y))
          (list (- half-x) 0.0))
        "0")
      (entmake '((0 . "ENDBLK") (100 . "AcDbEntity") (8 . "0")
                 (100 . "AcDbBlockEnd")))))
  name)

(defun pcap:insert-diamond (center block-name layer /)
  (entmakex
    (list
      '(0 . "INSERT")
      '(100 . "AcDbEntity")
      (cons 8 layer)
      '(100 . "AcDbBlockReference")
      (cons 2 block-name)
      (cons 10 center)
      '(41 . 1.0)
      '(42 . 1.0)
      '(43 . 1.0)
      '(50 . 0.0))))

(defun pcap:h-neck (left-center right-center half-x width layer / x1 x2 y h)
  (setq x1 (+ (car left-center) half-x)
        x2 (- (car right-center) half-x)
        y  (cadr left-center)
        h  (/ width 2.0))
  (if (> x2 x1)
    (pcap:closed-polyline
      (list (list x1 (+ y h)) (list x2 (+ y h))
            (list x2 (- y h)) (list x1 (- y h)))
      layer)))

(defun pcap:v-neck (lower-center upper-center half-y width layer / x y1 y2 h)
  (setq x  (car lower-center)
        y1 (+ (cadr lower-center) half-y)
        y2 (- (cadr upper-center) half-y)
        h  (/ width 2.0))
  (if (> y2 y1)
    (pcap:closed-polyline
      (list (list (- x h) y1) (list (+ x h) y1)
            (list (+ x h) y2) (list (- x h) y2))
      layer)))

(defun pcap:get-positive-real (message default / value)
  (initget 6)
  (setq value (getreal (strcat message " <" (rtos default 2 3) ">: ")))
  (if value value default))

(defun pcap:get-positive-int (message default / value)
  (initget 6)
  (setq value (getint (strcat message " <" (itoa default) ">: ")))
  (if value value default))

(defun c:PCAPDIAMOND
  (/ *error* old-cmdecho old-osmode undo-open origin rows cols pitch-x pitch-y
     gap neck half-x half-y diamond-block tx-layer rx-layer tx-route-layer rx-route-layer
     row col center previous x y)

  (setq old-cmdecho (getvar "CMDECHO")
        old-osmode  (getvar "OSMODE")
        undo-open   nil)

  (defun *error* (message)
    (if undo-open (command-s "_.UNDO" "_End"))
    (setvar "CMDECHO" old-cmdecho)
    (setvar "OSMODE" old-osmode)
    (if (and message
             (/= message "Function cancelled")
             (/= message "quit / exit abort"))
      (prompt (strcat "\nPCAPDIAMOND error: " message)))
    (princ))

  (setvar "CMDECHO" 0)
  (setq origin (getpoint "\nSelect lower-left lattice origin: "))
  (if origin
    (progn
      (setq rows    (pcap:get-positive-int  "TX electrode rows" 6)
            cols    (pcap:get-positive-int  "RX electrode columns" 10)
            pitch-x (pcap:get-positive-real "X electrode pitch" 5.0)
            pitch-y (pcap:get-positive-real "Y electrode pitch" 5.0)
            gap      (pcap:get-positive-real "Inter-electrode gap" 0.6)
            neck     (pcap:get-positive-real "Interconnect neck width" 0.5))

      (if (or (>= gap (* 2.0 pitch-x))
              (>= gap (* 2.0 pitch-y))
              (>= neck (- (* 2.0 pitch-x) gap))
              (>= neck (- (* 2.0 pitch-y) gap)))
        (prompt "\nInvalid geometry: gap or connector width is too large for the pitch.")
        (progn
          ;; Like-colored centers are two pitches apart. The half dimensions
          ;; leave the requested gap between their facing diamond vertices.
          (setq half-x (- pitch-x (/ gap 2.0))
                half-y (- pitch-y (/ gap 2.0))
                diamond-block  (pcap:ensure-diamond-block half-x half-y)
                tx-layer       (pcap:ensure-layer "PCAP_TX_ELECTRODE" 1)
                rx-layer       (pcap:ensure-layer "PCAP_RX_ELECTRODE" 5)
                tx-route-layer (pcap:ensure-layer "PCAP_TX_INTERCONNECT" 30)
                rx-route-layer (pcap:ensure-layer "PCAP_RX_INTERCONNECT" 150))

          (command-s "_.UNDO" "_Begin")
          (setq undo-open T
                row 0)

          ;; TX: horizontal chains on even lattice positions.
          (repeat rows
            (setq col 0
                  previous nil
                  y (+ (cadr origin) (* row 2.0 pitch-y)))
            (repeat cols
              (setq x (+ (car origin) (* col 2.0 pitch-x))
                    center (list x y))
              (pcap:insert-diamond center diamond-block tx-layer)
              (if previous
                (pcap:h-neck previous center half-x neck tx-route-layer))
              (setq previous center
                    col (1+ col)))
            (setq row (1+ row)))

          ;; RX: vertical chains offset by one pitch in both axes.
          (setq col 0)
          (repeat cols
            (setq row 0
                  previous nil
                  x (+ (car origin) pitch-x (* col 2.0 pitch-x)))
            (repeat rows
              (setq y (+ (cadr origin) pitch-y (* row 2.0 pitch-y))
                    center (list x y))
              (pcap:insert-diamond center diamond-block rx-layer)
              (if previous
                (pcap:v-neck previous center half-y neck rx-route-layer))
              (setq previous center
                    row (1+ row)))
            (setq col (1+ col)))

          (command-s "_.UNDO" "_End")
          (setq undo-open nil)
          (prompt
            (strcat "\nPCAPDIAMOND created " (itoa rows) " TX rows and "
                    (itoa cols) " RX columns on four dedicated layers.")))))
    (prompt "\nPCAPDIAMOND cancelled."))

  (setvar "CMDECHO" old-cmdecho)
  (setvar "OSMODE" old-osmode)
  (princ))

(prompt "\nPCAP Diamond Electrode Generator loaded. Run PCAPDIAMOND.")
(princ)
