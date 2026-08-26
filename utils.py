import face_recognition
import numpy as np
import os
import cv2  # OpenCV for image processing
from models import Person, db

# --- Photo to Sketch Conversion ---
def convert_to_sketch(image_path, output_path):
    """
    Converts an input image to a pencil sketch using OpenCV and saves it.
    """
    try:
        # Read the image using OpenCV
        img = cv2.imread(image_path)
        if img is None:
            print(f"Error: Could not read image from {image_path}")
            return False

        # 1. Convert the image to grayscale
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Invert the grayscale image to get a negative
        inverted_gray_img = 255 - gray_img

        # 3. Apply a strong Gaussian blur to the inverted image to soften it
        #    A larger kernel size (e.g., 111) makes the lines darker and thicker.
        blurred_img = cv2.GaussianBlur(inverted_gray_img, (111, 111), 0)

        # 4. Invert the blurred image
        inverted_blurred_img = 255 - blurred_img

        # 5. Create the pencil sketch by dividing the grayscale image by the inverted blurred image
        sketch_img = cv2.divide(gray_img, inverted_blurred_img, scale=256.0)
        
        # Save the final sketch image to the specified output path
        cv2.imwrite(output_path, sketch_img)
        return True
    except Exception as e:
        print(f"An error occurred during sketch conversion: {e}")
        return False


def convert_to_sketch_in_memory(image_bytes):
    """Converts image bytes to sketch bytes in memory."""
    try:
        # Decode the image from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Convert to grayscale
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Invert the grayscale image
        inverted_gray_image = 255 - gray_image

        # Apply a stronger Gaussian blur for darker lines
        blurred_image = cv2.GaussianBlur(inverted_gray_image, (121, 121), 0)

        # Invert the blurred image
        inverted_blurred_image = 255 - blurred_image

        # Create the pencil sketch by dividing the grayscale image by the inverted blurred image
        pencil_sketch = cv2.divide(gray_image, inverted_blurred_image, scale=256.0)

        # Encode the resulting sketch back to JPEG bytes
        is_success, buffer = cv2.imencode(".jpg", pencil_sketch)
        if is_success:
            return buffer.tobytes()
        else:
            return None
    except Exception as e:
        print(f"Error converting image to sketch in memory: {e}")
        return None


# --- Face Recognition Core Functions ---

def get_face_encoding(image_path):
    """
    Loads an image file and returns the face encoding for the first face found.
    Returns None if no face is found or an error occurs.
    """
    try:
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        if encodings:
            return encodings[0]  # Return the encoding of the first face
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
    return None

def serialize_encoding(encoding):
    """
    Converts a numpy array (face encoding) into a comma-separated string for database storage.
    """
    return ','.join(map(str, encoding))

def deserialize_encoding(encoding_str):
    """
    Converts a comma-separated string from the database back into a numpy array.
    """
    return np.array(encoding_str.split(','), dtype=float)

def find_matches(sketch_encoding, top_n=5):
    """
    Compares a given sketch encoding against all known persons in the database.
    Returns a list of the top N matches based on similarity.
    """
    persons = Person.query.all()
    if not persons:
        return []

    # Get all known encodings from the database
    known_encodings = [deserialize_encoding(p.face_encoding) for p in persons]
    
    # Calculate the distance between the sketch and all known faces.
    # A smaller distance means a better match.
    face_distances = face_recognition.face_distance(known_encodings, sketch_encoding)

    results = []
    for i, person in enumerate(persons):
        distance = face_distances[i]
        # Convert the distance metric (0.0 to 1.0+) to a more intuitive similarity percentage.
        # A distance of 0.0 is a 100% match. We use a simple linear conversion.
        similarity = max(0, (1 - distance) * 100) 
        
        # Only consider matches above a certain similarity threshold (e.g., 50%)
        if similarity > 50:
            results.append({
                'person': person,
                'similarity': round(similarity, 2)
            })

    # Sort the results to show the most similar faces first
    results.sort(key=lambda x: x['similarity'], reverse=True)

    return results[:top_n]

