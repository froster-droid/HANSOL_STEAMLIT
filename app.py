import streamlit as st
import pandas as pd
import smtplib
import io
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

st.set_page_config(page_title="엑셀 분석 & 메일 발송", layout="centered")
st.title("📊 엑셀 분석 & Gmail 발송")

# ── 파일 업로드 ──────────────────────────────────────────
uploaded = st.file_uploader("엑셀 파일 업로드 (.xlsx)", type=["xlsx"])

if uploaded:
    df = pd.read_excel(uploaded)

    product_col = df.columns[1]   # 제품
    date_col    = df.columns[0]   # 날짜
    total_col   = df.columns[-1]  # 총액

    # ── 미리보기 ─────────────────────────────────────────
    st.subheader("📋 원본 데이터 미리보기")
    st.dataframe(df, use_container_width=True)

    # ── Sheet 1: 100만원 이상 ────────────────────────────
    df_high = df[df[total_col] >= 1_000_000].copy()

    # ── Sheet 2: 제품별 총매출 ───────────────────────────
    df_product = (df.groupby(product_col)[total_col]
                  .sum()
                  .reset_index()
                  .sort_values(total_col, ascending=False)
                  .rename(columns={total_col: '총매출합산'}))

    # ── Sheet 3: 날짜별 총매출 ───────────────────────────
    df_date = (df.groupby(date_col)[total_col]
               .sum()
               .reset_index()
               .sort_values(date_col)
               .rename(columns={total_col: '총매출합산'}))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("100만원 이상 건수", f"{len(df_high)}건")
    with col2:
        st.metric("제품 종류", f"{len(df_product)}종")
    with col3:
        st.metric("날짜 수", f"{len(df_date)}일")

    # ── 엑셀 생성 (메모리) ───────────────────────────────
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_high.to_excel(writer, sheet_name='100만원이상', index=False)
        df_product.to_excel(writer, sheet_name='제품별총매출', index=False)
        df_date.to_excel(writer, sheet_name='날짜별총매출', index=False)
    excel_bytes = output.getvalue()

    st.download_button(
        "⬇️ 결과 엑셀 다운로드",
        data=excel_bytes,
        file_name="분석결과.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.divider()

    # ── 메일 발송 설정 ───────────────────────────────────
    st.subheader("📧 Gmail 발송 설정")

    with st.expander("🔐 Gmail 계정 설정", expanded=True):
        sender = st.text_input("발신자 Gmail 주소", placeholder="your@gmail.com")
        app_pw = st.text_input("앱 비밀번호", type="password",
                               help="Gmail → 보안 → 2단계인증 → 앱 비밀번호에서 생성")
        receiver = st.text_input("수신자 이메일 주소", placeholder="receiver@example.com")

    mail_subject = st.text_input("메일 제목", value="엑셀 분석 결과 전송")
    mail_body    = st.text_area("메일 본문", value="안녕하세요,\n\n엑셀 분석 결과 파일을 첨부합니다.\n\n감사합니다.", height=150)

    if st.button("📨 메일 발송", type="primary"):
        if not sender or not app_pw or not receiver:
            st.error("발신자, 앱 비밀번호, 수신자를 모두 입력해주세요.")
        else:
            try:
                msg = MIMEMultipart()
                msg['From']    = sender
                msg['To']      = receiver
                msg['Subject'] = mail_subject
                msg.attach(MIMEText(mail_body, 'plain', 'utf-8'))

                part = MIMEBase('application', 'octet-stream')
                part.set_payload(excel_bytes)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition',
                                'attachment; filename="분석결과.xlsx"')
                msg.attach(part)

                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(sender, app_pw)
                    server.sendmail(sender, receiver, msg.as_string())

                st.success(f"✅ {receiver} 으로 메일을 성공적으로 발송했습니다!")
            except smtplib.SMTPAuthenticationError:
                st.error("❌ 인증 실패 — Gmail 주소와 앱 비밀번호를 확인해주세요.")
            except Exception as e:
                st.error(f"❌ 발송 실패: {e}")
else:
    st.info("👆 엑셀 파일을 업로드하면 분석 결과와 메일 발송 기능이 활성화됩니다.")
