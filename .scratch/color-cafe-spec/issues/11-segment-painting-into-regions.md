# Research: splitting a painting into numbered color-by-number regions

Type: research
Status: open
Blocked by: 

## Question

Given a finished colour painting (e.g. puzzle-parlor/public/img/haunted-village.jpg or witch-kitchen.jpg at 2912px), how do we automatically produce a Happy-Color-style page: a palette of N colours (N roughly 20-40), every pixel assigned to one palette colour, regions = connected areas of one colour, tiny regions merged into neighbours so every region is tappable on a phone, outlines drawn between regions, and a number placed inside each region? Try it for real in this environment (OpenCV 5, Pillow, numpy are available; scikit-image is not): colour quantisation (k-means / median cut in a perceptual colour space), smoothing before quantising, min-region-size merging, outline extraction, number placement (largest inscribed point). Save sample outputs under research/segment/ and measure: region count, smallest tappable region, how recognisable the outline page is, and how close the 'all revealed' result is to the original painting (it should be the original pixels, so exact). Recommend a pipeline for the content tool and the data format the app loads (label map + palette + original image).
