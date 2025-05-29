from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
from io import BytesIO
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Global variables to store data
clients_df = pd.DataFrame()
payments_df = pd.DataFrame()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    global clients_df

    if 'file' not in request.files:
        flash('No file selected')
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('index'))

    if file and file.filename.endswith('.xlsx'):
        try:
            # Read the Excel file
            df = pd.read_excel(file)

            # Validate required columns
            required_columns = ['Account Manager', 'Client Name', 'Client ID', 'Arrears', 'Days Past Due']
            if not all(col in df.columns for col in required_columns):
                flash('Missing required columns in the file')
                return redirect(url_for('index'))

            # Categorize PAR
            df['PAR Category'] = pd.cut(
                df['Days Past Due'],
                bins=[0, 30, 60, float('inf')],
                labels=['PAR 1 (1-30)', 'PAR 2 (31-60)', 'PAR 3 (60+)'],
                right=False
            )

            clients_df = df
            flash('File uploaded successfully')
            return redirect(url_for('report'))

        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            return redirect(url_for('index'))

    else:
        flash('Invalid file format. Please upload an Excel file (.xlsx)')
        return redirect(url_for('index'))


@app.route('/report')
def report():
    global clients_df

    if clients_df.empty:
        flash('No data available. Please upload a file first.')
        return redirect(url_for('index'))

    # Group by Account Manager and PAR Category
    summary = clients_df.groupby(['Account Manager', 'PAR Category'])['Arrears'].sum().unstack().fillna(0)

    return render_template('report.html',
                           clients=clients_df.to_dict('records'),
                           summary=summary.to_dict())


@app.route('/upload_payment', methods=['POST'])
def upload_payment():
    global clients_df, payments_df

    if clients_df.empty:
        flash('No client data available. Upload client file first.')
        return redirect(url_for('index'))

    if 'payment_file' not in request.files:
        flash('No payment file selected')
        return redirect(url_for('report'))

    file = request.files['payment_file']
    if file.filename == '':
        flash('No payment file selected')
        return redirect(url_for('report'))

    if file and file.filename.endswith('.xlsx'):
        try:
            # Read payment file
            payment_data = pd.read_excel(file)

            # Validate required columns
            required_columns = ['Account Manager', 'Client ID', 'Payment Amount']
            if not all(col in payment_data.columns for col in required_columns):
                flash('Missing required columns in payment file')
                return redirect(url_for('report'))

            # Update clients_df with payments
            for _, row in payment_data.iterrows():
                mask = (clients_df['Account Manager'] == row['Account Manager']) & \
                       (clients_df['Client ID'] == row['Client ID'])

                if mask.any():
                    clients_df.loc[mask, 'Arrears'] -= row['Payment Amount']
                    # Update Days Past Due if payment covers full arrears
                    clients_df.loc[mask & (clients_df['Arrears'] <= 0), 'Days Past Due'] = 0
                else:
                    flash(f"Client {row['Client ID']} not found under {row['Account Manager']}")

            # Re-categorize PAR after payments
            clients_df['PAR Category'] = pd.cut(
                clients_df['Days Past Due'],
                bins=[0, 30, 60, float('inf')],
                labels=['PAR 1 (1-30)', 'PAR 2 (31-60)', 'PAR 3 (60+)'],
                right=False
            )

            payments_df = payment_data
            flash('Payments processed successfully')
            return redirect(url_for('report'))

        except Exception as e:
            flash(f'Error processing payment file: {str(e)}')
            return redirect(url_for('report'))

    else:
        flash('Invalid file format. Please upload an Excel file (.xlsx)')
        return redirect(url_for('report'))


@app.route('/summary')
def summary_report():
    global clients_df

    if clients_df.empty:
        flash('No data available. Please upload a file first.')
        return redirect(url_for('index'))

    # Create summary by account manager and PAR category
    summary = clients_df.groupby(['Account Manager', 'PAR Category'])['Arrears'] \
        .sum().unstack().fillna(0)

    # Calculate totals
    summary['Total'] = summary.sum(axis=1)

    return render_template('summary.html',
                           summary=summary.reset_index().to_dict('records'),
                           par_categories=['PAR 1 (1-30)', 'PAR 2 (31-60)', 'PAR 3 (60+)'])


if __name__ == '__main__':
    app.run(debug=True)