import os
import cv2
import numpy as np
import face_recognition

from models import Person


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

def _prepare_image(image):
    """
    Converts an OpenCV image into a normal 3-channel BGR image.

    Handles:
        - BGR images
        - BGRA images with transparency
        - grayscale images

    Transparent areas are converted to a white background.
    """

    if image is None:
        return None

    try:
        # ----------------------------------------------------
        # Grayscale image
        # ----------------------------------------------------
        if len(image.shape) == 2:
            return cv2.cvtColor(
                image,
                cv2.COLOR_GRAY2BGR
            )

        # ----------------------------------------------------
        # BGRA image
        # ----------------------------------------------------
        if len(image.shape) == 3 and image.shape[2] == 4:

            bgr = image[:, :, :3]
            alpha = image[:, :, 3]

            alpha = (
                alpha.astype(np.float32) / 255.0
            )

            alpha = alpha[:, :, None]

            white = np.full_like(
                bgr,
                255,
                dtype=np.uint8
            )

            result = (
                bgr.astype(np.float32) * alpha
                +
                white.astype(np.float32) * (1.0 - alpha)
            )

            return np.clip(
                result,
                0,
                255
            ).astype(np.uint8)

        # ----------------------------------------------------
        # Normal BGR image
        # ----------------------------------------------------
        if len(image.shape) == 3 and image.shape[2] == 3:
            return image

        print("Unsupported image format.")
        return None

    except Exception as e:
        print(
            f"Error preparing image: {e}"
        )
        return None


# ============================================================
# FACE DETECTION AND CROPPING
# ============================================================

def crop_face(image):
    """
    Detects the largest face and crops it with padding.

    Returns:
        Cropped BGR face image
        None if no face is detected
    """

    if image is None:
        return None

    try:

        image = _prepare_image(image)

        if image is None:
            return None

        # ----------------------------------------------------
        # Convert BGR → RGB
        # ----------------------------------------------------

        rgb = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB
        )

        # ----------------------------------------------------
        # First face detection attempt
        # ----------------------------------------------------

        locations = face_recognition.face_locations(
            rgb,
            number_of_times_to_upsample=1,
            model="hog"
        )

        # ----------------------------------------------------
        # Second attempt at higher resolution
        # ----------------------------------------------------

        if not locations:

            print(
                "Face not detected. "
                "Trying higher resolution..."
            )

            locations = face_recognition.face_locations(
                rgb,
                number_of_times_to_upsample=2,
                model="hog"
            )

        if not locations:

            print("No face detected.")
            return None

        # ----------------------------------------------------
        # Select largest face
        # ----------------------------------------------------

        def face_area(box):

            top, right, bottom, left = box

            return (
                (bottom - top)
                *
                (right - left)
            )

        top, right, bottom, left = max(
            locations,
            key=face_area
        )

        image_height, image_width = image.shape[:2]

        face_width = right - left
        face_height = bottom - top

        # ----------------------------------------------------
        # Add padding
        # ----------------------------------------------------

        padding_x = int(
            face_width * 0.35
        )

        padding_top = int(
            face_height * 0.40
        )

        padding_bottom = int(
            face_height * 0.30
        )

        left = max(
            0,
            left - padding_x
        )

        right = min(
            image_width,
            right + padding_x
        )

        top = max(
            0,
            top - padding_top
        )

        bottom = min(
            image_height,
            bottom + padding_bottom
        )

        face = image[
            top:bottom,
            left:right
        ]

        if face.size == 0:
            print("Face crop is empty.")
            return None

        return face

    except Exception as e:

        print(
            f"Error cropping face: {e}"
        )

        return None


# ============================================================
# PENCIL SKETCH GENERATION
# ============================================================

def _create_pencil_sketch(image):
    """
    Generates a clean pencil-style sketch.

    The function is designed for a cropped face image.
    """

    if image is None:
        return None

    try:

        image = _prepare_image(image)

        if image is None:
            return None

        # ----------------------------------------------------
        # 1. Resize
        # ----------------------------------------------------

        max_dimension = 1000

        height, width = image.shape[:2]

        if max(height, width) > max_dimension:

            scale = (
                max_dimension /
                float(max(height, width))
            )

            new_width = max(
                1,
                int(width * scale)
            )

            new_height = max(
                1,
                int(height * scale)
            )

            image = cv2.resize(
                image,
                (
                    new_width,
                    new_height
                ),
                interpolation=cv2.INTER_AREA
            )

        # ----------------------------------------------------
        # 2. Convert to grayscale
        # ----------------------------------------------------

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        # ----------------------------------------------------
        # 3. Improve contrast
        # ----------------------------------------------------

        clahe = cv2.createCLAHE(
            clipLimit=1.2,
            tileGridSize=(8, 8)
        )

        gray = clahe.apply(gray)

        # ----------------------------------------------------
        # 4. Reduce noise while preserving facial details
        # ----------------------------------------------------

        smooth = cv2.bilateralFilter(
            gray,
            d=9,
            sigmaColor=50,
            sigmaSpace=50
        )

        # ----------------------------------------------------
        # 5. Pencil shading
        # ----------------------------------------------------

        inverted = cv2.bitwise_not(
            smooth
        )

        blurred = cv2.GaussianBlur(
            inverted,
            (31, 31),
            0
        )

        denominator = (
            255 - blurred
        )

        # Prevent division by zero
        denominator = np.maximum(
            denominator,
            1
        ).astype(np.uint8)

        pencil = cv2.divide(
            smooth,
            denominator,
            scale=256
        )

        # ----------------------------------------------------
        # 6. Very subtle structural edges
        # ----------------------------------------------------

        edges = cv2.Canny(
            smooth,
            threshold1=60,
            threshold2=140
        )

        # Soften edges
        edges = cv2.GaussianBlur(
            edges,
            (3, 3),
            0
        )

        # Reduce edge intensity
        edge_strength = (
            edges.astype(np.float32)
            * 0.35
        )

        edge_strength = np.clip(
            edge_strength,
            0,
            255
        ).astype(np.uint8)

        edge_layer = (
            255 - edge_strength
        )

        # ----------------------------------------------------
        # 7. Combine pencil shading and subtle edges
        # ----------------------------------------------------

        sketch = cv2.multiply(
            pencil,
            edge_layer,
            scale=1.0 / 255.0
        )

        # ----------------------------------------------------
        # 8. Normalize
        # ----------------------------------------------------

        sketch = cv2.normalize(
            sketch,
            None,
            25,
            235,
            cv2.NORM_MINMAX
        )

        # ----------------------------------------------------
        # 9. Light smoothing
        # ----------------------------------------------------

        sketch = cv2.GaussianBlur(
            sketch,
            (3, 3),
            0
        )

        # ----------------------------------------------------
        # 10. Mild sharpening
        # ----------------------------------------------------

        blurred_sketch = cv2.GaussianBlur(
            sketch,
            (0, 0),
            1.0
        )

        sketch = cv2.addWeighted(
            sketch,
            1.08,
            blurred_sketch,
            -0.08,
            0
        )

        # ----------------------------------------------------
        # 11. Final brightness and contrast
        # ----------------------------------------------------

        sketch = cv2.convertScaleAbs(
            sketch,
            alpha=1.02,
            beta=10
        )

        return sketch

    except Exception as e:

        print(
            f"Error generating pencil sketch: {e}"
        )

        return None


# ============================================================
# PHOTO → SKETCH
# FILE VERSION
# ============================================================

def convert_to_sketch(
    image_path,
    output_path
):
    """
    Reads a photo, detects/crops the face,
    generates a pencil sketch and saves it.

    Returns:
        True  = successful
        False = failed
    """

    try:

        # ----------------------------------------------------
        # Check input
        # ----------------------------------------------------

        if not image_path:
            print("No input image path.")
            return False

        if not os.path.exists(image_path):

            print(
                f"Input image does not exist: "
                f"{image_path}"
            )

            return False

        # ----------------------------------------------------
        # Read with alpha support
        # ----------------------------------------------------

        image = cv2.imread(
            image_path,
            cv2.IMREAD_UNCHANGED
        )

        if image is None:

            print(
                f"Could not read image: "
                f"{image_path}"
            )

            return False

        # ----------------------------------------------------
        # Prepare image
        # ----------------------------------------------------

        image = _prepare_image(
            image
        )

        if image is None:
            return False

        # ----------------------------------------------------
        # Detect and crop face
        # ----------------------------------------------------

        face = crop_face(
            image
        )

        if face is None:

            print(
                "Could not detect a face "
                "in the input image."
            )

            return False

        # ----------------------------------------------------
        # Generate sketch
        # ----------------------------------------------------

        sketch = _create_pencil_sketch(
            face
        )

        if sketch is None:
            return False

        # ----------------------------------------------------
        # Create output directory
        # ----------------------------------------------------

        output_directory = os.path.dirname(
            os.path.abspath(output_path)
        )

        os.makedirs(
            output_directory,
            exist_ok=True
        )

        # ----------------------------------------------------
        # Save sketch
        # ----------------------------------------------------

        success = cv2.imwrite(
            output_path,
            sketch
        )

        if not success:

            print(
                f"Could not save sketch: "
                f"{output_path}"
            )

            return False

        print(
            f"Sketch successfully saved: "
            f"{output_path}"
        )

        return True

    except Exception as e:

        print(
            f"Error converting image to sketch: "
            f"{e}"
        )

        return False


# ============================================================
# PHOTO → SKETCH
# IN-MEMORY VERSION
# ============================================================

def convert_to_sketch_in_memory(
    image_bytes
):
    """
    Converts uploaded image bytes into a sketch.

    This is used by the Flask /photo-to-sketch route.

    Returns:
        JPEG bytes
        None on failure
    """

    try:

        # ----------------------------------------------------
        # Validate input
        # ----------------------------------------------------

        if not image_bytes:

            print(
                "Empty image data received."
            )

            return None

        # ----------------------------------------------------
        # Convert bytes → numpy array
        # ----------------------------------------------------

        nparr = np.frombuffer(
            image_bytes,
            np.uint8
        )

        # ----------------------------------------------------
        # Decode with alpha support
        # ----------------------------------------------------

        image = cv2.imdecode(
            nparr,
            cv2.IMREAD_UNCHANGED
        )

        if image is None:

            print(
                "Could not decode uploaded image."
            )

            return None

        # ----------------------------------------------------
        # Handle transparency
        # ----------------------------------------------------

        image = _prepare_image(
            image
        )

        if image is None:
            return None

        # ----------------------------------------------------
        # Detect and crop face
        # ----------------------------------------------------

        face = crop_face(
            image
        )

        if face is None:

            print(
                "No face detected in uploaded image."
            )

            return None

        # ----------------------------------------------------
        # Generate sketch
        # ----------------------------------------------------

        sketch = _create_pencil_sketch(
            face
        )

        if sketch is None:
            return None

        # ----------------------------------------------------
        # Encode as JPEG
        # ----------------------------------------------------

        success, buffer = cv2.imencode(
            ".jpg",
            sketch,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                95
            ]
        )

        if not success:

            print(
                "Could not encode sketch."
            )

            return None

        return buffer.tobytes()

    except Exception as e:

        print(
            f"Error converting image "
            f"to sketch in memory: {e}"
        )

        return None


# ============================================================
# FACE ENCODING
# ============================================================

def get_face_encoding(
    image_path
):
    """
    Generates a 128-dimensional face encoding.

    Returns:
        numpy array with shape (128,)
        None if no face/encoding is found.
    """

    try:

        if not image_path:
            return None

        if not os.path.exists(image_path):

            print(
                f"Image does not exist: "
                f"{image_path}"
            )

            return None

        # ----------------------------------------------------
        # Load image
        # ----------------------------------------------------

        image = face_recognition.load_image_file(
            image_path
        )

        if image is None:
            return None

        # ----------------------------------------------------
        # Detect face
        # ----------------------------------------------------

        locations = face_recognition.face_locations(
            image,
            number_of_times_to_upsample=1,
            model="hog"
        )

        # ----------------------------------------------------
        # Retry with higher resolution
        # ----------------------------------------------------

        if not locations:

            print(
                "Face not detected. "
                "Trying higher resolution..."
            )

            locations = face_recognition.face_locations(
                image,
                number_of_times_to_upsample=2,
                model="hog"
            )

        if not locations:

            print(
                f"No face detected: "
                f"{image_path}"
            )

            return None

        # ----------------------------------------------------
        # Generate encoding
        # ----------------------------------------------------

        encodings = face_recognition.face_encodings(
            image,
            known_face_locations=locations,
            num_jitters=1,
            model="small"
        )

        if not encodings:

            print(
                f"Could not generate encoding: "
                f"{image_path}"
            )

            return None

        encoding = np.asarray(
            encodings[0],
            dtype=np.float64
        )

        # ----------------------------------------------------
        # Validate encoding
        # ----------------------------------------------------

        if encoding.shape != (128,):

            print(
                f"Invalid encoding shape: "
                f"{encoding.shape}"
            )

            return None

        return encoding

    except Exception as e:

        print(
            f"Error processing face encoding: "
            f"{e}"
        )

        return None


# ============================================================
# SERIALIZE FACE ENCODING
# ============================================================

def serialize_encoding(
    encoding
):
    """
    Converts a 128-dimensional numpy encoding
    into a database-friendly string.
    """

    try:

        if encoding is None:
            return None

        encoding = np.asarray(
            encoding,
            dtype=np.float64
        )

        if encoding.shape != (128,):

            print(
                f"Cannot serialize invalid "
                f"encoding shape: {encoding.shape}"
            )

            return None

        return ",".join(
            format(
                float(value),
                ".17g"
            )
            for value in encoding
        )

    except Exception as e:

        print(
            f"Error serializing encoding: "
            f"{e}"
        )

        return None


# ============================================================
# DESERIALIZE FACE ENCODING
# ============================================================

def deserialize_encoding(
    encoding_str
):
    """
    Converts the database string back into
    a numpy face encoding.
    """

    try:

        if not encoding_str:
            return None

        values = encoding_str.split(",")

        encoding = np.asarray(
            values,
            dtype=np.float64
        )

        if encoding.shape != (128,):

            print(
                f"Invalid database encoding shape: "
                f"{encoding.shape}"
            )

            return None

        return encoding

    except Exception as e:

        print(
            f"Error deserializing encoding: "
            f"{e}"
        )

        return None


# ============================================================
# FIND MATCHES
# ============================================================

def find_matches(
    sketch_encoding,
    top_n=5
):
    """
    Compares an input sketch encoding against
    stored sketch encodings of academic test subjects.

    Smaller face distance = better match.

    Returns:
        List of potential matches.

    NOTE:
        The similarity score is a display metric,
        NOT an identity probability.
    """

    try:

        # ----------------------------------------------------
        # Validate input
        # ----------------------------------------------------

        if sketch_encoding is None:

            print(
                "No sketch encoding supplied."
            )

            return []

        sketch_encoding = np.asarray(
            sketch_encoding,
            dtype=np.float64
        )

        if sketch_encoding.shape != (128,):

            print(
                f"Invalid input encoding shape: "
                f"{sketch_encoding.shape}"
            )

            return []

        # ----------------------------------------------------
        # Get database records
        # ----------------------------------------------------

        print(
            f"QUERY SKETCH ENCODING: "
            f"shape={sketch_encoding.shape}, "
            f"dtype={sketch_encoding.dtype}"
        )

        persons = Person.query.all()

        if not persons:

            print(
                "No test subjects found in database."
            )

            return []

        known_encodings = []
        valid_persons = []

        # ----------------------------------------------------
        # Deserialize STORED SKETCH encodings
        # ----------------------------------------------------

        for person in persons:

            # IMPORTANT:
            # Recognition is now sketch-to-sketch.
            #
            # Do NOT use:
            # person.face_encoding
            #
            # Use:
            # person.sketch_encoding

            encoding = deserialize_encoding(
                person.sketch_encoding
            )

            if encoding is not None:

                known_encodings.append(
                    encoding
                )

                valid_persons.append(
                    person
                )

            else:

                print(
                    f"Skipping {person.name}: "
                    f"no valid sketch encoding found."
                )

        if not known_encodings:

            print(
                "No valid sketch encodings "
                "found in database."
            )

            return []

        # ----------------------------------------------------
        # Calculate face distances
        # ----------------------------------------------------

        distances = face_recognition.face_distance(
            known_encodings,
            sketch_encoding
        )

        # ----------------------------------------------------
        # DEBUG: show every database distance
        # ----------------------------------------------------

        print("\n========== SKETCH MATCHING DEBUG ==========")

        for person, distance in zip(
            valid_persons,
            distances
        ):

            print(
                f"Subject: {person.name} | "
                f"Sketch Distance: {float(distance):.4f}"
            )

        if len(distances) > 0:

            best_index = int(
                np.argmin(distances)
            )

            print(
                f"BEST SUBJECT: "
                f"{valid_persons[best_index].name} | "
                f"BEST SKETCH DISTANCE: "
                f"{float(distances[best_index]):.4f}"
            )

        print(
            "MATCH THRESHOLD: 0.6000"
        )

        print(
            "=========================================\n"
        )

        # ----------------------------------------------------
        # Build results
        # ----------------------------------------------------

        results = []

        # Demo threshold
        MATCH_THRESHOLD = 0.60

        for person, distance in zip(
            valid_persons,
            distances
        ):

            distance = float(
                distance
            )

            # ------------------------------------------------
            # Convert distance to display score
            # ------------------------------------------------

            similarity = (
                1.0 -
                (
                    distance /
                    MATCH_THRESHOLD
                )
            ) * 100.0

            similarity = max(
                0.0,
                min(
                    100.0,
                    similarity
                )
            )

            # ------------------------------------------------
            # Only show candidates inside threshold
            # ------------------------------------------------

            if distance <= MATCH_THRESHOLD:

                results.append({
                    "person": person,

                    "similarity": round(
                        similarity,
                        2
                    ),

                    "distance": round(
                        distance,
                        4
                    )
                })

        # ----------------------------------------------------
        # Best distance first
        # ----------------------------------------------------

        results.sort(
            key=lambda item:
            item["distance"]
        )

        return results[:top_n]

    except Exception as e:

        print(
            f"Error while finding matches: "
            f"{e}"
        )

        return []