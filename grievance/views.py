# views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from .models import User, Grievance
from .serializers import *
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import HttpResponse
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils.timezone import now
from django.conf import settings
import os
from .models import ChatMessage
from .ai_recommender import get_matching_keywords

# 🔐 TOKEN GENERATE
def get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }

# ✅ REGISTER
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({"msg": "Registered"})
    return Response(serializer.errors)


# ✅ LOGIN
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    email = request.data.get("email")
    password = request.data.get("password")
    
    
    if not email or not password:
        return Response(
            {"detail": "Email and password required"},
            status=400
        )

    user = User.objects.filter(email=email).first()

    if user and user.check_password(password):
        tokens = get_tokens(user)

        return Response({
            "access": tokens["access"],   # ✅ FIXED
            "refresh": tokens["refresh"], # ✅ FIXED
            "role": (user.role or "").upper() if user.role else "",
            "full_name": user.full_name or "",
            "email": user.email,
            "department": user.department or ""
        })

    return Response({"detail": "Invalid credentials"}, status=400)

# ✅ PROFILE
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    serializer = RegisterSerializer(request.user)
    return Response(serializer.data)


# ✅ UPDATE PROFILE
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    serializer = RegisterSerializer(user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({"msg": "Updated"})
    return Response(serializer.errors)


# ✅ CREATE GRIEVANCE
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_grievance(request):
    data = request.data.copy()
    data['submitted_by'] = request.user.id

    serializer = GrievanceSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response({"msg": "Created"})
    return Response(serializer.errors)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard(request):
    
    if request.user.role != "ADMIN":
        return Response(
            {"error": "Unauthorized"},
            status=403
        )

    # only department grievances
    grievances = Grievance.objects.filter(
        department=request.user.department
    )
    serializer = GrievanceSerializer(grievances, many=True)

    faculty = User.objects.filter(role="FACULTY", department=request.user.department)

    faculty_list = [
        {
            "id": f.id,
            "name": f.full_name,
            "email": f.email,
            "department": f.department,
            "specialization": f.specialization
        }
        for f in faculty
    ]

    return Response({
        "department": request.user.department,
        "grievances": serializer.data,
        "faculty_list": faculty_list
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_grievance(request):
    if request.user.role != "ADMIN":
        return Response({"error": "Unauthorized"}, status=403)

    gid = request.data.get("grievance_id")
    faculty_id = request.data.get("faculty_id")
    message = request.data.get("message")

    try:
        grievance = Grievance.objects.get(grievance_id=gid)
        faculty = User.objects.get(id=faculty_id)
    except:
        return Response({"error": "Invalid data"}, status=400)

    grievance.assigned_to = faculty
    grievance.assigned_message = message   # ✅ FIXED
    grievance.status = "ASSIGNED"
    grievance.save()

    return Response({"msg": "Assigned successfully"})

# ✅ STUDENT DASHBOARD
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_dashboard(request):
    grievances = Grievance.objects.filter(submitted_by=request.user)
    serializer = GrievanceSerializer(grievances, many=True)

    return Response({
        "data": serializer.data,
        "total": grievances.count(),
        "pending": grievances.filter(status="NEW").count(),
        "in_progress": grievances.filter(status="IN_PROGRESS").count(),
        "resolved": grievances.filter(status="RESOLVED").count(),
    })


# ✅ FACULTY DASHBOARD
from django.db.models import Q

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def faculty_dashboard(request):

    data = Grievance.objects.filter(
        assigned_to=request.user
    )

    serializer = GrievanceSerializer(
        data,
        many=True
    )

    assigned_data = serializer.data

    for grievance in assigned_data:

        # Combine grievance text
        grievance_text = (
            f"{grievance.get('subject', '')} "
            f"{grievance.get('description', '')} "
            f"{grievance.get('category', '')}"
        ).lower()

        # Get all staff
        all_staff = User.objects.filter(
            role="STAFF"
        ).exclude(
            staff_function__isnull=True
        ).exclude(
            staff_function=""
        )

        matched_keywords = get_matching_keywords(
            grievance_text
        )

        recommended = []

        for staff in all_staff:

            staff_function = (
                staff.staff_function or ""
            ).lower()

            # SMART KEYWORD MATCH
            if any(
                 keyword in staff_function
                 for keyword in matched_keywords
            ):
                recommended.append({
                    "name": staff.full_name,
                    "email": staff.email,
                    "phone": staff.phone_number,
                    "function": staff.staff_function
                })

        # Fallback if no matches
        if not recommended:
            
            fallback_staff = all_staff.filter(
                 Q(staff_function__icontains="technical") |
                 Q(staff_function__icontains="worker") |
                 Q(staff_function__icontains="maintenance")
            )
             
            recommended = [
                {
                    "name": s.full_name,
                    "email": s.email,
                    "phone": s.phone_number,
                    "function": s.staff_function
                }
                for s in all_staff[:5]
            ]

        grievance["recommended_staff"] = recommended

    return Response({
        "assigned": assigned_data
    })

# ✅ UPDATE STATUS
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_status(request):
    gid = request.data.get("grievance_id")
    grievance = Grievance.objects.get(grievance_id=gid)

    grievance.status = request.data.get("status")
    grievance.faculty_remark = request.data.get("remark")
    if request.FILES.get("resolution_image"):
        grievance.resolution_image = request.FILES.get(
             "resolution_image"
        )
      
    grievance.save()

    return Response({"msg": "Updated"})

@api_view(['GET'])
@permission_classes([AllowAny])
def public_analytics(request):

    total = Grievance.objects.count()

    status_distribution = list(
        Grievance.objects.values('status')
        .annotate(count=Count('status'))
    )

    monthly_trend = list(
        Grievance.objects
        .filter(date_filed__isnull=False)
        .annotate(month=TruncMonth('date_filed'))
        .values('month')
        .annotate(count=Count('grievance_id'))   # ✅ FIXED
        .order_by('month')
    )

    department_wise = list(
        Grievance.objects.values('department')
        .annotate(count=Count('grievance_id'))    # ✅ FIXED
    )

    # 🔥 NEW: DEPARTMENT + STATUS MATRIX (POWER BI STYLE)
    dept_status = list(
        Grievance.objects
        .values('department', 'status')
        .annotate(count=Count('grievance_id'))
    )

    return Response({
        "total": total,
        "status_distribution": status_distribution,
        "monthly_trend": monthly_trend,
        "department_wise": department_wise,
        "dept_status": dept_status   # 🔥 NEW
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_analytics(request):
    try:
        if request.user.role != "ADMIN":
            return Response({"error": "Unauthorized"}, status=403)

        dept = request.user.department

        qs = Grievance.objects.filter(department=dept)

        # ✅ TOTAL
        total = qs.count()

        # ✅ STATUS
        status_distribution = list(
            qs.values('status').annotate(count=Count('status'))
        )

        # ✅ MONTHLY TREND
        monthly_trend = list(
            qs.annotate(month=TruncMonth('date_filed'))
            .values('month')
            .annotate(count=Count('grievance_id'))
            .order_by('month')
        )

        # ✅ NEW: CATEGORY-WISE (MAIN INSIGHT)
        category_wise = list(
            qs.values('category')
            .annotate(count=Count('grievance_id'))
        )

        return Response({
            "department": dept,
            "total": total,
            "status_distribution": status_distribution,
            "monthly_trend": monthly_trend,
            "category_wise": category_wise   # ✅ NEW
        })

    except Exception as e:
        print("ADMIN ANALYTICS ERROR:", str(e))
        return Response({"error": "Server error"}, status=500)

# grievance_report

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    HRFlowable,
    KeepTogether
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER

from reportlab.lib.styles import ParagraphStyle

from xml.sax.saxutils import escape

from django.http import HttpResponse

import os
from datetime import datetime


# PAGE BORDER
def draw_page_border(canvas, doc):

    canvas.saveState()

    canvas.setStrokeColor(
        colors.HexColor("#4338CA")
    )

    canvas.setLineWidth(2)

    canvas.rect(
        20,
        20,
        A4[0] - 40,
        A4[1] - 40
    )

    canvas.restoreState()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def grievance_report(request, id):

    try:

        grievance = Grievance.objects.get(
            grievance_id=id
        )

    except Grievance.DoesNotExist:

        return Response(
            {"error": "Grievance not found"},
            status=404
        )

    try:

        response = HttpResponse(
            content_type='application/pdf'
        )

        response['Content-Disposition'] = (
            f'attachment; filename="grievance_{id}.pdf"'
        )

        doc = SimpleDocTemplate(
            response,
            pagesize=A4,
            rightMargin=35,
            leftMargin=35,
            topMargin=30,
            bottomMargin=30
        )

        styles = getSampleStyleSheet()

        # =========================
        # TITLE STYLE
        # =========================
        title_style = ParagraphStyle(
            'title',
            parent=styles['Title'],
            alignment=TA_CENTER,
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1E3A8A"),
            spaceAfter=2
        )

        # =========================
        # SUBTITLE STYLE
        # =========================
        subtitle_style = ParagraphStyle(
            'subtitle',
            parent=styles['Heading2'],
            alignment=TA_CENTER,
            fontSize=14,
            textColor=colors.HexColor("#111827"),
            spaceAfter=2
        )

        # =========================
        # SECTION STYLE
        # =========================
        section_style = ParagraphStyle(
            'section',
            parent=styles['Heading2'],
            textColor=colors.HexColor("#4338CA"),
            fontSize=16,
            spaceAfter=10
        )

        # =========================
        # NORMAL STYLE
        # =========================
        normal_style = styles['BodyText']

        elements = []

        # =========================
        # SAFE TEXT
        # =========================
        safe_subject = escape(
            grievance.subject or ""
        )

        safe_description = escape(
            grievance.description or ""
        )

        safe_remark = escape(
            grievance.faculty_remark or "No remarks added."
        )

        # =========================
        # LOGO PATH
        # =========================
        BASE_DIR = os.path.dirname(
            os.path.dirname(
               os.path.abspath(__file__)
            )
        )

        logo_path = os.path.join(
            BASE_DIR,
            "logo.png"
        )

        print("LOGO PATH:", logo_path)
        print("LOGO EXISTS:", os.path.exists(logo_path))

        # =========================
        # HEADER SECTION
        # =========================

        # LOGO
        if os.path.exists(logo_path):

            logo = Image(
                logo_path,
                width=1.0 * inch,
                height=1.0 * inch
            )

        else:

            logo = ""

        # TITLE + SUBTITLE
        title_content = [

            Paragraph(
                "L.D. College of Engineering",
                title_style
            ),

            Paragraph(
                "AI-Powered Grievance Redressal System",
                subtitle_style
            )
        ]

        # HEADER TABLE
        header_table = Table(

            [[logo, title_content]],

            colWidths=[80, 420]
        )

        header_table.setStyle(TableStyle([

            (
                'VALIGN',
                (0, 0),
                (-1, -1),
                'MIDDLE'
            ),

            (
                'ALIGN',
                (0, 0),
                (0, 0),
                'LEFT'
            ),

            (
                'ALIGN',
                (1, 0),
                (1, 0),
                'CENTER'
            ),

            (
                'LEFTPADDING',
                (0, 0),
                (-1, -1),
                0
            ),

            (
                'RIGHTPADDING',
                (0, 0),
                (-1, -1),
                0
            ),

            (
                'TOPPADDING',
                (0, 0),
                (-1, -1),
                0
            ),

            (
                'BOTTOMPADDING',
                (0, 0),
                (-1, -1),
                0
            ),

        ]))

        elements.append(
            KeepTogether(header_table)
        )

        elements.append(
            Spacer(1, 10)
        )

        # =========================
        # HEADER LINE
        # =========================
        elements.append(
            HRFlowable(
                width="100%",
                thickness=2,
                color=colors.HexColor("#4338CA")
            )
        )

        elements.append(
            Spacer(1, 15)
        )

        # =========================
        # REPORT TITLE
        # =========================
        elements.append(
            Paragraph(
                f"<b>Official Grievance Report #{grievance.grievance_id}</b>",
                section_style
            )
        )

        # =========================
        # GENERATED DATE
        # =========================
        generated_time = datetime.now().strftime(
            "%d %B %Y | %I:%M %p"
        )

        elements.append(
            Paragraph(
                f"<b>Generated On:</b> {generated_time}",
                normal_style
            )
        )

        # =========================
        # GENERATED BY
        # =========================
        elements.append(
            Paragraph(
                f"<b>Generated By:</b> {request.user.full_name}",
                normal_style
            )
        )

        elements.append(
            Spacer(1, 15)
        )

        # =========================
        # STATUS COLOR
        # =========================
        status_color = colors.red

        if grievance.status == "RESOLVED":

            status_color = colors.green

        elif grievance.status == "IN_PROGRESS":

            status_color = colors.blue

        elif grievance.status == "ASSIGNED":

            status_color = colors.orange

        # =========================
        # STATUS BADGE
        # =========================
        status_text = grievance.status.replace(
            "_",
            " "
        )

        status_para = Paragraph(

            f"""
            <font color="white">
            <b>STATUS : {status_text}</b>
            </font>
            """,

            ParagraphStyle(
                'status',
                backColor=status_color,
                alignment=TA_CENTER,
                fontSize=12,
                leading=14,
                spaceAfter=15,
                borderPadding=8
            )
        )
        elements.append(status_para)

        # =========================
        # TABLE DATA
        # =========================
        data = [

            ["Field", "Information"],

            [
                "Grievance ID",
                str(grievance.grievance_id)
            ],

            [
                "Subject",
                safe_subject
            ],

            [
                "Department",
                grievance.department or "N/A"
            ],

            [
                "Category",
                grievance.category or "N/A"
            ],

            [
                "Status",
                status_text
            ],

            [
                "Assigned Faculty",

                grievance.assigned_to.full_name
                if grievance.assigned_to
                else "Not Assigned"
            ],

            [
                "Date Filed",

                grievance.date_filed.strftime(
                    "%d %B %Y | %I:%M %p"
                )

                if grievance.date_filed
                else "N/A"
            ],
        ]

        # =========================
        # MAIN TABLE
        # =========================
        table = Table(
            data,
            colWidths=[180, 300]
        )

        table.setStyle(TableStyle([

            (
                'BACKGROUND',
                (0, 0),
                (-1, 0),
                colors.HexColor("#4338CA")
            ),

            (
                'TEXTCOLOR',
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                'FONTNAME',
                (0, 0),
                (-1, 0),
                'Helvetica-Bold'
            ),

            (
                'FONTSIZE',
                (0, 0),
                (-1, -1),
                11
            ),

            (
                'BOTTOMPADDING',
                (0, 0),
                (-1, 0),
                12
            ),

            (
                'BACKGROUND',
                (0, 1),
                (0, -1),
                colors.HexColor("#EEF2FF")
            ),

            (
                'GRID',
                (0, 0),
                (-1, -1),
                1,
                colors.HexColor("#D1D5DB")
            ),

            (
                'BOX',
                (0, 0),
                (-1, -1),
                1.5,
                colors.HexColor("#4338CA")
            ),

            (
                'ROWBACKGROUNDS',
                (1, 1),
                (-1, -1),
                [
                    colors.white,
                    colors.HexColor("#F9FAFB")
                ]
            ),

            (
                'LEFTPADDING',
                (0, 0),
                (-1, -1),
                10
            ),

            (
                'RIGHTPADDING',
                (0, 0),
                (-1, -1),
                10
            ),

            (
                'TOPPADDING',
                (0, 0),
                (-1, -1),
                7
            ),

            (
                'BOTTOMPADDING',
                (0, 0),
                (-1, -1),
                7
            ),

            (
                'VALIGN',
                (0, 0),
                (-1, -1),
                'MIDDLE'
            ),

        ]))

        elements.append(table)

        elements.append(
            Spacer(1, 25)
        )

        # =========================
        # DESCRIPTION
        # =========================
        elements.append(
            Paragraph(
                "1. Detailed Description",
                section_style
            )
        )

        elements.append(
            Paragraph(
                safe_description,
                normal_style
            )
        )

        elements.append(
            Spacer(1, 20)
        )

        # =========================
        # FACULTY REMARK
        # =========================
        elements.append(
            Paragraph(
                "2. Faculty Remark",
                section_style
            )
        )

        elements.append(
            Paragraph(
                safe_remark,
                normal_style
            )
        )

        elements.append(
            Spacer(1, 20)
        )

        # =========================
        # AI ANALYSIS
        # =========================
        elements.append(
            Paragraph(
                "3. AI Analysis",
                section_style
            )
        )

        elements.append(
            Paragraph(
                "The AI engine automatically categorized "
                "and analyzed this grievance for faster "
                "institutional response and smart workflow handling.",
                normal_style
            )
        )

        elements.append(
            Spacer(1, 20)
        )

        # =========================
        # EVIDENCE IMAGE
        # =========================
        if grievance.image:

            try:

                elements.append(
                    Paragraph(
                        "4. Attached Evidence",
                        section_style
                    )
                )

                elements.append(
                    Spacer(1, 10)
                )

                evidence = Image(
                    grievance.image.path,
                    width=5.2 * inch,
                    height=3.5 * inch
                )

                evidence.hAlign = 'CENTER'

                evidence_table = Table(
                    [[evidence]],
                    colWidths=[380]
                )

                evidence_table.setStyle(TableStyle([

                    (
                        'BOX',
                        (0, 0),
                        (-1, -1),
                        1.5,
                        colors.HexColor("#D1D5DB")
                    ),

                    (
                        'BACKGROUND',
                        (0, 0),
                        (-1, -1),
                        colors.HexColor("#F9FAFB")
                    ),

                    (
                        'ALIGN',
                        (0, 0),
                        (-1, -1),
                        'CENTER'
                    ),

                    (
                        'TOPPADDING',
                        (0, 0),
                        (-1, -1),
                        10
                    ),

                    (
                        'BOTTOMPADDING',
                        (0, 0),
                        (-1, -1),
                        10
                    ),

                ]))

                elements.append(evidence_table)

                elements.append(
                    Spacer(1, 18)
                )

            except Exception as img_error:

                print(
                    "IMAGE ERROR:",
                    img_error
                )

        # =========================
        # SIGNATURE SECTION
        # =========================
        elements.append(
            Spacer(1, 15)
        )

        sign_table = Table(

            [
                [
                    "_______________________",
                    "_______________________"
                ],

                [
                    "Applicant Signature",
                    "Authority Signature"
                ]
            ],

            colWidths=[220, 220]
        )

        sign_table.setStyle(TableStyle([

            (
                'ALIGN',
                (0, 0),
                (-1, -1),
                'CENTER'
            ),

            (
                'TOPPADDING',
                (0, 0),
                (-1, -1),
                8
            ),

            (
                'FONTSIZE',
                (0, 1),
                (-1, 1),
                10
            ),

        ]))

        elements.append(sign_table)

        # =========================
        # FOOTER
        # =========================
        elements.append(
            Spacer(1, 15)
        )

        footer = Paragraph(

            "<font color='#6B7280'>"
            "<i>This is a digitally generated official grievance report.</i>"
            "</font>",

            ParagraphStyle(
                'footer',
                alignment=TA_CENTER,
                fontSize=9
            )
        )

        elements.append(footer)

        # =========================
        # BUILD PDF
        # =========================
        doc.build(

            elements,

            onFirstPage=draw_page_border,

            onLaterPages=draw_page_border
        )

        return response

    except Exception as e:

        print("PDF ERROR:", str(e))

        return Response(
            {"error": str(e)},
            status=500
        )

# --------------------------------
# CHATBOT API (SMART RULE-BASED)
# --------------------------------

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Grievance


@api_view(['POST'])
@permission_classes([AllowAny])
def chatbot_response(request):

    msg = request.data.get("message", "").strip().lower()
    msg = msg.replace("grivance", "grievance")
    msg = msg.replace("grivannce", "grievance")
    msg = msg.replace("complain", "complaint")
    user = request.user if request.user.is_authenticated else None

    # Latest grievance of current user
    latest = None
    if user:
        latest = (
            Grievance.objects
            .filter(submitted_by=user)
            .order_by("-date_filed")
            .first()
        )

    answer = ""

    # --------------------------------
    # GREETINGS
    # --------------------------------
    if any(word in msg for word in ["hi", "hello", "hey", "hii"]):

        name = user.full_name if user else "Guest"

        answer = (
            f"Hello {name} 👋\n\n"
            "I’m LDCE Grievance AI Assistant.\n\n"
            "How can I help you today?\n\n"
            "You can ask:\n"
            "• What is grievance?\n"
            "• How to register?\n"
            "• Is registration compulsory?\n"
            "• How to file grievance?\n"
            "• What is my complaint status?\n"
            "• Staff role options\n"
            "• How to download report?"
        )

    # --------------------------------
    # WHAT IS GRIEVANCE
    # --------------------------------
    elif (
        "what is grievance" in msg or
        "what is grivance" in msg or
        "grievance meaning" in msg
    ):

        answer = (
            "A grievance is a complaint or issue you submit "
            "through this portal for academic, faculty, "
            "infrastructure, or administrative problems."
        )

    # --------------------------------
    # HOW CAN YOU HELP
    # --------------------------------
    elif (
        "how can you help" in msg or
        "help me" in msg or
        msg == "help"
    ):

        answer = (
            "I can help you with:\n\n"
            "• Registration guidance\n"
            "• Filing a grievance\n"
            "• Checking grievance status\n"
            "• Downloading grievance reports\n"
            "• Explaining grievance statuses\n"
            "• Showing assigned faculty\n"
            "• Explaining portal features"
        )

    # --------------------------------
    # REGISTRATION COMPULSORY
    # --------------------------------
    elif (
        "is registration compulsory" in msg or
        "it is compulsory to register" in msg or
        "must i register" in msg or
        "do i need to register" in msg or
        "registration required" in msg
    ):

        answer = (
            "Yes, registration is required to file and track a grievance.\n\n"
            "You can use this chatbot without logging in, "
            "but to submit a complaint or check your personal grievance status, "
            "you need to register and log in."
        )

    # --------------------------------
    # HOW TO REGISTER
    # --------------------------------
    elif (
        "how to register" in msg or
        "registration process" in msg or
        "how do i register" in msg or
        "create account" in msg
    ):

        answer = (
            "To register:\n\n"
            "1. Click 'Register' on the home page\n"
            "2. Enter your full name\n"
            "3. Enter email and password\n"
            "4. Select your role (Student / Staff / Faculty)\n"
            "5. Fill required details\n"
            "6. Submit registration\n\n"
            "After registration, login to access all features."
        )

    # --------------------------------
    # STAFF ROLE OPTIONS
    # --------------------------------
    elif (
        "staff type" in msg or
        "staff role" in msg or
        "what staff options" in msg or
        "staff function" in msg
    ):

        answer = (
            "During staff registration, you can choose your staff function such as:\n\n"
            "• Worker\n"
            "• Security\n"
            "• Management\n"
            "• Administrative Staff\n"
            "• Technical Staff\n\n"
            "If your role is not listed, select 'Other' and enter your function manually."
        )

    # --------------------------------
    # CUSTOM STAFF FUNCTION
    # --------------------------------
    elif (
        "custom staff function" in msg or
        "add my own function" in msg or
        "my role is not listed" in msg or
        "other option" in msg
    ):

        answer = (
            "Yes. If your staff role is not available in the list, "
            "choose 'Other' during registration and type your function manually."
        )

    # --------------------------------
    # WHO CAN FILE GRIEVANCE
    # --------------------------------
    elif (
        "who can file grievance" in msg or
        "who can submit complaint" in msg or
        "who can use this portal" in msg
    ):

        answer = (
            "Students, Staff, and Faculty members of LDCE "
            "can register and file grievances through this portal."
        )

    # --------------------------------
    # FILE GRIEVANCE
    # --------------------------------
    elif (
        "file grievance" in msg or
        "how to file grievance" in msg or
        "new complaint" in msg or
        "file complaint" in msg
    ):

        answer = (
            "To file a grievance:\n\n"
            "1. Open 'File Complaint'\n"
            "2. Enter subject\n"
            "3. Enter description\n"
            "4. Select category\n"
            "5. Upload evidence (optional)\n"
            "6. Submit"
        )

    # --------------------------------
    # COMPLAINT STATUS
    # --------------------------------
    elif (
        "status" in msg or
        "complaint status" in msg or
        "my grievance" in msg
    ):

        if latest:
            faculty_name = (
                latest.assigned_to.full_name
                if latest.assigned_to
                else "Not assigned"
            )

            remark = (
                latest.faculty_remark
                if latest.faculty_remark
                else "No remark yet"
            )

            answer = (
                f"Your grievance status:\n\n"
                f"Subject: {latest.subject}\n"
                f"Status: {latest.status}\n"
                f"Faculty: {faculty_name}\n"
                f"Remark: {remark}"
            )
        else:
            answer = (
                "I couldn't find any grievance linked to your account yet.\n\n"
                "If you haven't submitted one, you can file a grievance from the dashboard."
            )

    # --------------------------------
    # ASSIGNED FACULTY
    # --------------------------------
    elif (
        "assigned faculty" in msg or
        "show faculty" in msg or
        "assigned to" in msg
    ):

        if latest and latest.assigned_to:
            answer = (
                f"Your grievance is assigned to "
                f"{latest.assigned_to.full_name}."
            )
        else:
            answer = "No faculty has been assigned to your grievance yet."

    # --------------------------------
    # DOWNLOAD REPORT
    # --------------------------------
    elif (
        "download" in msg or
        "report" in msg or
        "download report" in msg
    ):

        answer = (
            "Go to your dashboard and click "
            "'Download Report' beside your grievance."
        )

    # --------------------------------
    # STATUS MEANINGS
    # --------------------------------
    elif "assigned" in msg:
        answer = (
            "ASSIGNED means your grievance "
            "has been assigned to faculty for review."
        )

    elif "in progress" in msg:
        answer = (
            "IN_PROGRESS means faculty is currently "
            "working on your issue."
        )

    elif "resolved" in msg:
        answer = (
            "RESOLVED means your grievance "
            "has been solved successfully."
        )

    elif "new" in msg:
        answer = (
            "NEW means your grievance "
            "has been received by the system."
        )

    # --------------------------------
    # THANK YOU
    # --------------------------------
    elif "thank" in msg or "thanks" in msg:
        answer = (
            "You're welcome 😊\n"
            "I'm happy to help."
    
        )

    # --------------------------------
# GRIEVANCE ANALYTICS
# --------------------------------
    elif any(
    phrase in msg
    for phrase in [

        # total grievance
        "total grievance",
        "total grievances",
        "total grivance",
        "how many grievance",
        "how many grievances",
        "available grievance",
        "available grievances",

        # pending
        "pending grievance",
        "pending grievances",
        "how much grievance is pending",
        "how many pending",
        "pending complaints",

        # resolved
        "resolved grievance",
        "resolved complaints",

        # analytics
        "analytics",
        "grievance analytics",
        "complaint analytics",

        # dashboard
        "grievance stats",
        "portal stats"
    ]
    ):

     total = Grievance.objects.count()
 
     pending = Grievance.objects.filter(
        status="NEW"
     ).count()

     progress = Grievance.objects.filter(
        status="IN_PROGRESS"
     ).count()

     resolved = Grievance.objects.filter(
        status="RESOLVED"
     ).count()

     assigned = Grievance.objects.filter(
        status="ASSIGNED"
     ).count()

     answer = (
        f"📊 LDCE Grievance Statistics\n\n"

        f"Total Grievances: {total}\n"
        f"Pending: {pending}\n"
        f"Assigned: {assigned}\n"
        f"In Progress: {progress}\n"
        f"Resolved: {resolved}"
    )
    elif "which department has most complaints" in msg:

      top = (
        Grievance.objects
        .values("department")
        .annotate(count=Count("grievance_id"))
        .order_by("-count")
        .first()
      )

      answer = (
        f"Department with highest grievances:\n\n"
        f"{top['department']} ({top['count']} complaints)"
      )

    elif "most common issue" in msg:

      top = (
        Grievance.objects
        .values("category")
        .annotate(count=Count("grievance_id"))
        .order_by("-count")
        .first()
      )

      answer = (
        f"Most common grievance category:\n"
        f"{top['category']} ({top['count']})"
      )
    
    # --------------------------------
# ABOUT LDCE SYSTEM
# --------------------------------
    elif (
    "ldce" in msg or
    "ldce grievance system" in msg or
    "about ldce" in msg or
    "about portal" in msg
    ):

     answer = (
        "LDCE Grievance Portal is a smart grievance "
        "management system developed for LD College of Engineering.\n\n"

        "The portal helps students, faculty, and staff:\n\n"

        "• File grievances online\n"
        "• Track complaint status\n"
        "• Upload supporting evidence\n"
        "• Receive faculty actions\n"
        "• Download grievance reports\n"
        "• Get AI-based assistance\n\n"

        "The system improves transparency, tracking, "
        "and grievance resolution efficiency."
    )

    # --------------------------------
    # FALLBACK RESPONSE
    # --------------------------------
    else:
        answer = (
            "I may not have understood your question fully, "
            "but I’d still like to help.\n\n"
            "You can try asking things like:\n\n"
            "• What is grievance?\n"
            "• How to register?\n"
            "• Is registration compulsory?\n"
            "• How to file grievance?\n"
            "• What is my complaint status?\n"
            "• Staff role options\n"
            "• How to download report?"
        )

    return Response({
        "reply": answer
    })

import os

from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.contrib.auth import get_user_model
from email.mime.image import MIMEImage
from rest_framework.response import Response

from .models import DepartmentMeeting, Notification


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_meeting(request):

    # =========================
    # ADMIN CHECK
    # =========================
    if request.user.role != "ADMIN":
        return Response(
            {"error": "Unauthorized"},
            status=403
        )

    data = request.data

    # =========================
    # CREATE MEETING
    # =========================
    meeting = DepartmentMeeting.objects.create(
        title=data.get("title"),
        description=data.get("description"),
        department=request.user.department,
        meeting_type=data.get("meeting_type"),
        meeting_link=data.get("meeting_link"),
        meeting_location=data.get("meeting_location"),
        meeting_datetime=data.get("meeting_datetime"),
        created_by=request.user
    )

    User = get_user_model()

    # =========================
    # GET FACULTY MEMBERS
    # =========================
    faculty_members = User.objects.filter(
        role="FACULTY",
        department=request.user.department
    )

    # =========================
    # LOGO PATH
    # =========================
    BASE_DIR = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    logo_path = os.path.join(
        BASE_DIR,
        "logo.png"
    )

    print("LOGO PATH:", logo_path)
    print("LOGO EXISTS:", os.path.exists(logo_path))

    # =========================
    # SEND EMAIL TO EACH FACULTY
    # =========================
    for faculty in faculty_members:

        # =========================
        # CREATE NOTIFICATION
        # =========================
        Notification.objects.create(
            user=faculty,
            message=f"Meeting scheduled: {meeting.title}"
        )

        # =========================
        # HTML EMAIL CONTENT
        # =========================
        html_content = f"""
        <html>
        <body style="
            font-family:Arial;
            background:#f4f6f8;
            padding:20px;
        ">

        <div style="
            max-width:600px;
            margin:auto;
            background:white;
            padding:20px;
            border-radius:10px;
            box-shadow:0px 2px 10px rgba(0,0,0,0.1);
        ">

            <div style="text-align:center; margin-bottom:20px;">

                <img
                    src="cid:company_logo"
                    style="width:120px;"
                />

            </div>

            <h2 style="color:#1e3a8a;">
                Department New Meeting
            </h2>

            <p>
                <b>Title:</b>
                {meeting.title}
            </p>

            <p>
                <b>Description:</b><br>
                {meeting.description}
            </p>

            <p>
                <b>Date:</b>
                {meeting.meeting_datetime}
            </p>

            <p>
                <b>Type:</b>
                {meeting.meeting_type}
            </p>

            <p>
                <b>Link/Location:</b><br>
                {meeting.meeting_link or meeting.meeting_location}
            </p>

            <hr>

            <p style="
                font-size:12px;
                color:gray;
                text-align:center;
            ">
                LDCE Grievance System Notification
            </p>

        </div>

        </body>
        </html>
        """

        # =========================
        # TEXT VERSION
        # =========================
        text_content = strip_tags(html_content)

        # =========================
        # CREATE EMAIL
        # =========================
        email = EmailMultiAlternatives(
            subject="New Department Meeting Scheduled",
            body=text_content,
            from_email="your-email@gmail.com",
            to=[faculty.email]
        )

        # =========================
        # ATTACH HTML
        # =========================
        email.attach_alternative(
            html_content,
            "text/html"
        )

        # =========================
        # ATTACH LOGO IMAGE
        # =========================
        with open(logo_path, "rb") as f:

            logo = MIMEImage(
                 f.read(),
                  _subtype="png"
            )

            logo.add_header(
                'Content-ID',
                '<company_logo>'
            )

            logo.add_header(
                'Content-Disposition',
                'inline',
                filename='logo.png'
            )

            email.attach(logo)

        # =========================
        # SEND EMAIL
        # =========================
        email.send(fail_silently=False)

    # =========================
    # RESPONSE
    # =========================
    return Response({
        "msg": "Meeting created and faculty notified"
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def faculty_notifications(request):

    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')

    data = [
        {
            "id": n.id,
            "message": n.message,
            "created_at": n.created_at
        }
        for n in notifications
    ]

    return Response(data)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):

    try:

        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )

        notification.delete()

        return Response({
            "message": "Notification deleted successfully"
        })

    except Notification.DoesNotExist:

        return Response(
            {"error": "Notification not found"},
            status=404
        )

    except Exception as e:

        return Response(
            {"error": str(e)},
            status=500
        )

import random
# from django.core.mail import send_mail
from .models import EmailOTP

@api_view(['POST'])
@permission_classes([AllowAny])
def send_registration_otp(request):

    email = request.data.get("email")

    if not email:
        return Response({"error": "Email required"}, status=400)

    # prevent duplicate account
    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already registered"}, status=400)

    # ✅ generate OTP ONLY ONCE
    otp = str(random.randint(100000, 999999))

    # save OTP
    EmailOTP.objects.update_or_create(
        email=email,
        defaults={"otp": otp}
    )

    # DEBUG ONLY (remove in production)
    print("OTP GENERATED:", otp)

    return Response({
        "msg": "OTP generated successfully",
        "otp": otp   # remove later in production
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_and_register(request):

    email = request.data.get("email")
    otp = request.data.get("otp")

    if not email or not otp:
        return Response({"error": "Email and OTP required"}, status=400)

    otp_obj = EmailOTP.objects.filter(email=email, otp=otp).first()

    if not otp_obj:
        return Response({"error": "Invalid OTP"}, status=400)

    if not otp_obj.is_valid():
        return Response({"error": "OTP expired"}, status=400)

    serializer = RegisterSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        otp_obj.delete()

        return Response({"msg": "Registration successful"})

    return Response(serializer.errors, status=400)








# @api_view(['POST'])
# @permission_classes([AllowAny])
# def send_registration_otp(request):

#     email = request.data.get("email")

#     if not email:
#         return Response(
#             {"error": "Email required"},
#             status=400
#         )

#     # prevent duplicate account
#     if User.objects.filter(email=email).exists():
#         return Response(
#             {"error": "Email already registered"},
#             status=400
#         )

#     otp = str(
#         random.randint(100000, 999999)
#     )

#     EmailOTP.objects.update_or_create(
#         email=email,
#         defaults={
#             "otp": otp
#         }
#     )

#     # send_mail(
#     #     "College Registration OTP",
#     #     f"Your OTP is: {otp}",
#     #     settings.EMAIL_HOST_USER,
#     #     [email],
#     #     fail_silently=False
#     # )
#     otp = str(random.randint(100000, 999999))

#     EmailOTP.objects.update_or_create(
#     email=email,
#     defaults={"otp": otp}
#     )

#     return Response({
#        "msg": "OTP generated",
#     })

# @api_view(['POST'])
# @permission_classes([AllowAny])
# def verify_otp_and_register(request):

#     email = request.data.get("email")
#     otp = request.data.get("otp")

#     otp_obj = EmailOTP.objects.filter(
#         email=email,
#         otp=otp
#     ).first()

#     if not otp_obj:
#         return Response(
#             {"error": "Invalid OTP"},
#             status=400
#         )

#     if not otp_obj.is_valid():
#         return Response(
#             {"error": "OTP expired"},
#             status=400
#         )

#     serializer = RegisterSerializer(
#         data=request.data
#     )

#     if serializer.is_valid():
#         serializer.save()

#         otp_obj.delete()

#         return Response({
#             "msg": "Registration successful"
#         })

#     return Response(
#         serializer.errors,
#         status=400
#     )
