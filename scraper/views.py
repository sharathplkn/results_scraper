import os
import csv
import time
import zipfile
import requests
from django.shortcuts import render
from django.core.files.storage import default_storage
from django.http import HttpResponse
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager

# Set a safe, writable download directory inside the app directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app_dir = os.path.join(BASE_DIR, 'results_scraper')  # Replace with your app's directory name
download_dir = os.path.join(app_dir, 'downloads')
os.makedirs(download_dir, exist_ok=True)

def upload_csv(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        download_link=request.POST.get('download_link')
        file_path = default_storage.save('temp.csv', csv_file)

        firefox_options = Options()
        firefox_options.set_preference("browser.download.folderList", 2)  # Custom download folder
        firefox_options.set_preference("browser.download.dir", download_dir)  # Set the download directory
        firefox_options.set_preference("browser.download.useDownloadDir", True)  # Automatically download files
        firefox_options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf")  # Accept PDFs without prompts
        firefox_options.set_preference("pdfjs.disabled", True)  # Disable the built-in PDF viewer
        firefox_options.add_argument("--headless")  # Run Firefox in headless mode (no UI)

        driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=firefox_options)

        with open(default_storage.path(file_path), newline='') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header if present

            for row in reader:
                try:
                    regno, dob = row[0].strip(), row[1].strip()

                    driver.get(download_link)

                    wait = WebDriverWait(driver, 1)
                    wait.until(EC.presence_of_element_located((By.ID, "regno"))).send_keys(regno)
                    driver.find_element(By.NAME, "dob").send_keys(dob)

                    

                    driver.find_element(By.XPATH, "//input[@type='button']").click()

                    # Wait for the download link to appear
                    wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Download Result")))
                    link = driver.find_element(By.LINK_TEXT, "Download Result")
                    download_url = link.get_attribute("href")  # Get the download URL

                    # Make a request to download the file without prompts
                    pdf_response = requests.get(download_url, stream=True)
                    if pdf_response.status_code == 200:
                        pdf_path = os.path.join(download_dir, f"{regno}.pdf")  # This ensures the filename matches the register number
                        with open(pdf_path, 'wb') as f:
                            for chunk in pdf_response.iter_content(chunk_size=1024):
                                if chunk:
                                    f.write(chunk)

                except Exception as e:
                    print(f"Error for {row}: {e}")
                    continue

        driver.quit()

        pdf_files = [f for f in os.listdir(download_dir) if f.lower().endswith('.pdf')]
        # Zip all PDFs in the download_dir
        if not pdf_files:
            return HttpResponse("No PDFs were downloaded.", status=500)

        zip_path = os.path.join(download_dir, 'results.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in pdf_files:
                full_path = os.path.join(download_dir, file)
                zipf.write(full_path, file)

        # Remove the downloaded PDFs from the directory after zipping
        for file in pdf_files:
            os.remove(os.path.join(download_dir, file))

        with open(zip_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename=results.zip'
            return response

    return render(request, 'scraper/upload.html')
