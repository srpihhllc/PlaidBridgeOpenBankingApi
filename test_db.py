import pymysql

try:
    conn = pymysql.connect(
        host="srpihhllc.mysql.pythonanywhere-services.com",
        user="srpihhllc",
        password="MierNumiernufirst",
        database="srpihhllc$default",
    )

    print("✅ RAW CONNECTION SUCCESSFUL!")

    conn.close()

except Exception as e:
    print(f"❌ RAW CONNECTION FAILED: {e}")
