import json, sys
for f in sys.argv[1:]:
    d=json.load(open(f))
    print(f"\n--- {d['page']} CPU throttle x{d['cpuThrottle']} ---")
    for r in d['results']:
        print(f"{r['W']}px prep(draw+getImageData+grey)={r['prepMs']}ms putImageData(full)={r['putImageDataFullMs']}ms composite(multiply)={r['compositeMultiplyMsPerFrame']}ms/frame")
        for T in (128,200):
            fl=r[f'floodT{T}']; l=r[f'labelT{T}']; sp=sorted(fl['samplePx'])
            print(f"   T={T} flood: worst {fl['worstPx']}px {fl['worstMs']}ms, median {fl['medianPx']}px {fl['medianMs']}ms; sample px={sp[:6]}...{sp[-3:]}")
            print(f"   T={T} label: {l['regions']} regions in {l['labelMs']}ms (+bbox {l['bboxMs']}ms, {l['labelBytesMB']}MB); fill largest {l['fillLargestPx']}px {l['fillLargestMs']}ms; median region {l['fillMedianPx']}px {l['fillMedianMs']}ms")
