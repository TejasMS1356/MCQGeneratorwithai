import os
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from processing import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_txt,
    summarize_text,
    generate_mcqs,
    save_results_to_memory
)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected!', 'error')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('No file selected!', 'error')
            return redirect(request.url)
            
        if not allowed_file(file.filename):
            flash('Invalid file type! Allowed: PDF, DOCX, TXT', 'error')
            return redirect(request.url)

        try:
            # Save uploaded file temporarily
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Extract text based on file type
            file_extension = os.path.splitext(filename)[1].lower()
            if file_extension == '.pdf':
                text = extract_text_from_pdf(file_path)
            elif file_extension == '.docx':
                text = extract_text_from_docx(file_path)
            elif file_extension == '.txt':
                text = extract_text_from_txt(file_path)
                
            if not text:
                raise ValueError("Could not extract text from file")

            # Process text
            summary = summarize_text(text)
            if not summary:
                raise ValueError("Failed to generate summary")

            mcqs = generate_mcqs(summary)
            if not mcqs:
                raise ValueError("Failed to generate MCQs")

            # Clean up temporary file
            os.remove(file_path)

            return render_template('results.html', 
                                 summary=summary, 
                                 mcqs=mcqs,
                                 original_filename=filename)

        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            flash(str(e), 'error')
            return redirect(request.url)

    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    try:
        summary = request.form['summary']
        mcqs = request.form['mcqs']
        output_format = request.form.get('output_format', 'pdf')
        filename = request.form.get('original_filename', 'output')

        # Generate file in memory
        output_data = save_results_to_memory(summary, mcqs, output_format)
        
        # Determine MIME type
        mimetypes = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'csv': 'text/csv'
        }
        
        return send_file(
            output_data,
            mimetype=mimetypes.get(output_format, 'application/octet-stream'),
            as_attachment=True,
            download_name=f"{filename}_results.{output_format}"
        )
        
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)