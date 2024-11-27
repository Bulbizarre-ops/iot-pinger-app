#----
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)

def generate_wifi_qr(ssid, authentication, password, hidden):
    # Construct Wi-Fi QR Code string
    wifi_string = f"WIFI:T:{authentication};S:{ssid};P:{password};H:{'true' if hidden else 'false'};;"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(wifi_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a UI on top of a dataframe to let viewers filter columns

    Args:
        df (pd.DataFrame): Original dataframe

    Returns:
        pd.DataFrame: Filtered dataframe
    """
    modify = st.checkbox("Add filters")

    if not modify:
        return df

    df = df.copy()

    # Try to convert datetimes into a standard format (datetime, no timezone)
    for col in df.columns:
        if is_object_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception:
                pass

        if is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)

    modification_container = st.container()

    with modification_container:
        to_filter_columns = st.multiselect("Filter data on", df.columns)
        for column in to_filter_columns:
            left, right = st.columns((1, 20))
            # Treat columns with < 10 unique values as categorical
            if is_categorical_dtype(df[column]) or df[column].nunique() < 10:
                user_cat_input = right.multiselect(
                    f"Values for {column}",
                    df[column].unique(),
                    default=list(df[column].unique()),
                )
                df = df[df[column].isin(user_cat_input)]
            elif is_numeric_dtype(df[column]):
                _min = float(df[column].min())
                _max = float(df[column].max())
                step = (_max - _min) / 100
                user_num_input = right.slider(
                    f"Values for {column}",
                    min_value=_min,
                    max_value=_max,
                    value=(_min, _max),
                    step=step,
                )
                df = df[df[column].between(*user_num_input)]
            elif is_datetime64_any_dtype(df[column]):
                user_date_input = right.date_input(
                    f"Values for {column}",
                    value=(
                        df[column].min(),
                        df[column].max(),
                    ),
                )
                if len(user_date_input) == 2:
                    user_date_input = tuple(map(pd.to_datetime, user_date_input))
                    start_date, end_date = user_date_input
                    df = df.loc[df[column].between(start_date, end_date)]
            else:
                user_text_input = right.text_input(
                    f"Substring or regex in {column}",
                )
                if user_text_input:
                    df = df[df[column].astype(str).str.contains(user_text_input)]

    return df

#---

# Create tabs for the two views
st.title("Welcome to the Multi-Feature App :balloon:")
tab1, tab2 = st.tabs(["Pinger Results", "Wi-Fi QR Code Generator"])

# Tab for Pinger Results
with tab1:
    st.header("Pinger Results")
    st.write(
        """You will be able to choose the selected device by entering its UUID
        """
    )

    # Get the device UUID
    device_UUID = st.text_input("Please enter the device UUID")

    if device_UUID:
        try:
            # Validate and format the UUID
            device_UUID_formatted = uuid.UUID(hex=device_UUID)
            st.write("You are looking for the test triggered by", device_UUID_formatted)

            # Fetch session
            cnx = st.connection("snowflake")
            session = cnx.session()

            # Query the database
            speed_results_dataframe = (
                session.table("IOT.PINGER.SPEED_TESTS_RESULTS")
                .filter(col("DEVICE_UUID") == str(device_UUID_formatted))
                .select(
                    col("END_DATE"),
                    col("AVG_UPLOAD_SPEED"),
                    col("AVG_DOWNLOAD_SPEED"),
                    col("AVG_PING")
                ).sort(col("END_DATE").desc())
                .to_pandas()
            )
            filtered_dataframe = filter_dataframe(speed_results_dataframe)
            st.line_chart(
                data=filtered_dataframe,
                x='END_DATE',
                y=['AVG_UPLOAD_SPEED', 'AVG_DOWNLOAD_SPEED'],
            )
            st.dataframe(filtered_dataframe)

        except ValueError:
            st.error("The entered UUID is invalid. Please check the format and try again.")

# Tab for Wi-Fi QR Code Generator
with tab2:
    st.header("Wi-Fi QR Code Generator")
    ssid = st.text_input("SSID (Wi-Fi Network Name)", "")
    authentication = st.selectbox("Authentication Type", ["WPA3-SAE", "WPA2-PSK", "OPEN"])
    password = st.text_input("Password", "", type="password") if authentication != "OPEN" else ""
    hidden = st.checkbox("Hidden SSID", False)

    # Generate QR Code button
    if st.button("Generate QR Code"):
        if not ssid:
            st.error("SSID is required!")
        elif authentication != "OPEN" and not password:
            st.error("Password is required for selected authentication!")
        else:
            # Generate and display QR Code
            img = generate_wifi_qr(ssid, authentication, password, hidden)
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            st.image(buffer, caption="Wi-Fi QR Code", use_column_width=True)
            st.download_button("Download QR Code", data=buffer, file_name="wifi_qr_code.png", mime="image/png")
