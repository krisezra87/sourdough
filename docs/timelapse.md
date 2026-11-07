Goal: time-lapse of sourdough starter jars in the pantry to find the peak time for different feed ratios and flours.

Step 1: add the new Reolink Argus Eco Ultra to HA (Reolink integration), enable its snapshot entity (disabled by default), and confirm a snapshot works. Check wake time and battery; power it continuously if possible.

Step 2: automation, every 30 min: turn on light.pantry_lights, wait ~15 s for camera wake, camera.snapshot to /media/starter/YYYYMMDD_HHMM.jpg, restore the light's previous state. Make sure it doesn't conflict with the existing "Pantry light on motion" automation.

Setup: 3 identical Bonne Maman jars, total feed <=100g each, one mark per jar at the starting level, and a fixed piece of tape in the frame as a reference for camera shifts. Log feed time, ratio, and flour for each jar.

Analysis: for each jar, measure the surface row in each photo, compute height relative to the jar bottom and start mark, smooth lightly, and report the peak time (maximum, confirmed by two or three consecutive lower readings). Verify a few images by eye.

First: calibration shots of all jars to check framing, glare, and visibility of the surface before the overnight run.
