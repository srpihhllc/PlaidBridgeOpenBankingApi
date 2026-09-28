import subprocess
from fpdf import FPDF

# Execute the inspection script and capture the stdout/stderr
print("Running inspect_app.py...")
result = subprocess.run(["python", "inspect_app.py"], capture_output=True, text=True)
output = result.stdout + result.stderr

# Initialize PDF with a monospace font for console alignment
pdf = FPDF()
pdf.add_page()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.set_font("Courier", size=8)

# Write the output line by line, handling FPDF's latin-1 text constraints
for line in output.split('\n'):
    clean_line = line.encode('latin-1', 'replace').decode('latin-1')
    pdf.cell(0, 4, txt=clean_line, ln=True)

pdf.output("console_output.pdf")
print("PDF generated successfully: console_output.pdf")