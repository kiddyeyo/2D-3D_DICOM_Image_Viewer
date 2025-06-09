import streamlit as st
import numpy as np
import tempfile
import os
import zipfile
import pydicom
import nibabel as nib
from skimage.measure import marching_cubes
import plotly.graph_objects as go
import io

st.set_page_config(page_title="CT 2D & 3D Viewer", layout="wide")

@st.cache_data
def load_nifti(buffer) -> np.ndarray:
    import nibabel as nib
    img = nib.load(buffer)
    return img.get_fdata()

@st.cache_data
def load_dicom_zip(zip_bytes) -> np.ndarray:
    tmp = tempfile.mkdtemp()
    with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as z:
        z.extractall(tmp)
    # find DICOM files
    paths = []
    for root, _, files in os.walk(tmp):
        for f in files:
            if f.lower().endswith('.dcm'):
                paths.append(os.path.join(root, f))
    slices = [pydicom.dcmread(p) for p in sorted(paths)]
    slices.sort(key=lambda s: float(getattr(s, 'ImagePositionPatient', [0,0,0])[2]))
    vol = np.stack([s.pixel_array for s in slices])
    return vol

st.title("CT 2D & 3D STL Viewer")

upload = st.file_uploader("Upload NIfTI (.nii/.nii.gz) or DICOM ZIP", type=['nii','nii.gz','zip'])
if upload:
    ext = os.path.splitext(upload.name)[1].lower()
    if ext in ['.nii', '.nii.gz']:
        volume = load_nifti(upload)
    elif ext == '.zip':
        volume = load_dicom_zip(upload.getvalue())
    else:
        st.error("Unsupported file type")
        st.stop()

    # compute window defaults
    vmin, vmax = np.percentile(volume, [1, 99])
    st.sidebar.header("Settings")
    orientation = st.sidebar.selectbox("Orientación", ['Axial','Coronal','Sagital'])
    if orientation == 'Axial': axis = 0
    elif orientation == 'Coronal': axis = 1
    else: axis = 2
    slice_idx = st.sidebar.slider("Slice", 0, volume.shape[axis]-1, volume.shape[axis]//2)
    center = st.sidebar.slider("Window Center", int(vmin), int(vmax), int((vmin+vmax)/2))
    width = st.sidebar.slider("Window Width", 1, int(vmax-vmin), int(vmax-vmin))
    thr = st.sidebar.slider("Threshold", int(vmin), int(vmax), int((vmin+vmax)/2))

    # extract slice
    if axis == 0:
        img = volume[slice_idx]
    elif axis == 1:
        img = volume[:, slice_idx]
    else:
        img = volume[:, :, slice_idx]
    mn, mx = center - width/2, center + width/2
    imgw = np.clip(img, mn, mx)
    disp = ((imgw - mn)/width * 255).astype(np.uint8)
    mask = img > thr

    # layout 2D view
    col1, col2 = st.columns([3,1])
    with col1:
        st.image(disp, use_column_width=True, clamp=True)
        st.image(np.ma.masked_where(~mask, mask), use_column_width=True, clamp=True)
    with col2:
        st.write(f"Slice: {slice_idx}/{volume.shape[axis]-1}")
        st.write(f"Window: [{mn:.1f}, {mx:.1f}]")
        st.write(f"Threshold: {thr}")

    # generate STL mesh
    if st.button("Generate & Show 3D Mesh"):
        verts, faces, _, _ = marching_cubes((volume > thr).astype(np.uint8), level=0)
        x, y, z = verts.T
        i, j, k = faces.T
        mesh = go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, opacity=0.5, color='lightblue')
        fig = go.Figure(mesh)
        fig.update_layout(width=800, height=800,
                          scene=dict(aspectmode='data'))
        st.plotly_chart(fig, use_container_width=True)

        # download STL
        st.download_button(
            "Download STL",
            data=create_stl_bytes(verts, faces),
            file_name="segmentation.stl",
            mime="application/octet-stream"
        )


@st.cache_data

def create_stl_bytes(verts, faces):
    buffer = io.BytesIO()
    writer = vtk.vtkSTLWriter()
    # build PolyData
    poly = vtk.vtkPolyData()
    pts = vtk.vtkPoints(); pts.SetData(numpy_to_vtk(verts))
    poly.SetPoints(pts)
    cells = vtk.vtkCellArray()
    for f in faces:
        cells.InsertNextCell(3)
        cells.InsertCellPoint(int(f[0])); cells.InsertCellPoint(int(f[1])); cells.InsertCellPoint(int(f[2]))
    poly.SetPolys(cells)
    writer.SetOutputString(True)
    writer.SetFileTypeToASCII()
    writer.SetInputData(poly)
    writer.WriteToOutputStringOn()
    writer.Write()
    data = writer.GetOutputString()
    return data
