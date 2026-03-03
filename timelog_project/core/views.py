import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from .models import Attendance, SalaryDamage, Table, TableSession, User, WorkMode
from .forms import CorrectionForm


# ─────────────────────────────────────────────
# Decorators
# ─────────────────────────────────────────────
def agent_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role not in ('agent', 'mami', 'admin') and not request.user.is_superuser:
            messages.error(request, '您沒有權限存取此頁面')
            return redirect('clock')
        return view_func(request, *args, **kwargs)
    return wrapper


def _get_agent_shop(user):
    """取得 agent/mami 管理的分店，admin 取第一間。"""
    if user.shop:
        return user.shop
    if user.role == 'admin' or user.is_superuser:
        company = user.effective_company
        if company:
            return company.shops.first()
    return None


# ─────────────────────────────────────────────
# General
# ─────────────────────────────────────────────
def home(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.role in ('agent', 'mami', 'admin') or request.user.is_superuser:
        return redirect('agent_daily')
    return redirect('clock')


# ─────────────────────────────────────────────
# Staff Views
# ─────────────────────────────────────────────
@login_required
def clock_view(request):
    user = request.user
    today = timezone.localdate()
    now = timezone.now()

    open_attendance = Attendance.objects.filter(
        user=user,
        clock_out__isnull=True,
        clock_in__date=today,
        status=Attendance.Status.NORMAL,
    ).order_by('-clock_in').first()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'clock_in':
            if open_attendance:
                messages.warning(request, '您已打上班卡，請先打下班卡。')
            else:
                segment = int(request.POST.get('segment', 1))
                Attendance.objects.create(user=user, clock_in=now, work_segment=segment)
                local_time = timezone.localtime(now).strftime('%H:%M')
                messages.success(request, f'上班打卡成功！時間：{local_time}，第 {segment} 班')
            return redirect('clock')

        elif action == 'clock_out':
            if not open_attendance:
                messages.warning(request, '找不到今日的上班記錄。')
            else:
                open_attendance.clock_out = now
                open_attendance.save()
                hours = open_attendance.duration_hours or 0
                messages.success(request, f'下班打卡成功！本次工時：{hours} 小時')
            return redirect('clock')

    working_duration = None
    if open_attendance:
        delta = now - open_attendance.clock_in
        h, rem = divmod(int(delta.total_seconds()), 3600)
        working_duration = f'{h} 時 {rem // 60:02d} 分'

    context = {
        'open_attendance': open_attendance,
        'working_duration': working_duration,
        'today': today,
        'now': timezone.localtime(now),
    }
    return render(request, 'staff/clock.html', context)


@login_required
def journal_view(request):
    user = request.user
    today = timezone.localdate()

    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    attendances = Attendance.objects.filter(
        user=user, clock_in__year=year, clock_in__month=month,
    ).order_by('-clock_in')

    valid = [a for a in attendances if a.status in ('normal', 'approved')]
    total_days = len({a.clock_in.date() for a in valid})
    total_hours = round(sum(a.duration_hours or 0 for a in valid), 1)

    missing_clockout = [
        a for a in attendances
        if a.clock_out is None and a.clock_in.date() < today and a.status == 'normal'
    ]
    pending_corrections = [a for a in attendances if a.status == 'pending_correction']

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    context = {
        'attendances': attendances,
        'total_days': total_days,
        'total_hours': total_hours,
        'missing_clockout': missing_clockout,
        'pending_corrections': pending_corrections,
        'year': year, 'month': month,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'today': today,
        'is_current_month': (year == today.year and month == today.month),
    }
    return render(request, 'staff/journal.html', context)


@login_required
def correction_create(request):
    if request.method == 'POST':
        form = CorrectionForm(request.POST, request.FILES)
        if form.is_valid():
            user = request.user
            c_type = form.cleaned_data['correction_type']
            date = form.cleaned_data['date']
            time = form.cleaned_data['time']
            note = form.cleaned_data['note']
            proof = form.cleaned_data['proof']
            corrected_dt = timezone.make_aware(datetime.datetime.combine(date, time))

            if c_type == 'missed_in':
                Attendance.objects.create(
                    user=user, clock_in=corrected_dt,
                    status=Attendance.Status.PENDING_CORRECTION, note=note, proof=proof,
                )
                messages.success(request, '補打上班卡申請已送出，待經紀人審核。')

            elif c_type == 'missed_out':
                open_att = Attendance.objects.filter(
                    user=user, clock_in__date=date,
                    clock_out__isnull=True, status=Attendance.Status.NORMAL,
                ).order_by('-clock_in').first()

                if open_att:
                    open_att.clock_out = corrected_dt
                    open_att.status = Attendance.Status.PENDING_CORRECTION
                    open_att.note = note
                    open_att.proof = proof
                    open_att.save()
                    messages.success(request, '補打下班卡申請已送出，待經紀人審核。')
                else:
                    messages.error(request, f'找不到 {date} 的未打下班記錄，請確認日期是否正確。')
                    return render(request, 'staff/correction_form.html', {'form': form})

            return redirect('journal')
    else:
        form = CorrectionForm()

    return render(request, 'staff/correction_form.html', {'form': form})


# ─────────────────────────────────────────────
# Agent Views
# ─────────────────────────────────────────────
@agent_required
def agent_daily(request):
    user = request.user
    today = timezone.localdate()
    now = timezone.now()

    shop = _get_agent_shop(user)
    if not shop:
        messages.error(request, '您尚未綁定分店，請聯繫管理員')
        return redirect('clock')

    date_str = request.GET.get('date', str(today))
    try:
        view_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        view_date = today

    # All active staff in this shop
    all_staff = User.objects.filter(shop=shop, role='staff', is_active=True).order_by('employee_code')

    # Attendances for this date (normal + approved)
    day_attendances = list(
        Attendance.objects.filter(
            user__shop=shop,
            clock_in__date=view_date,
            status__in=['normal', 'approved'],
        ).select_related('user').order_by('clock_in')
    )

    # Clocked out (completed attendance records)
    clocked_out_atts = [a for a in day_attendances if a.clock_out is not None]

    # Currently working (no clock_out)
    working_atts = [a for a in day_attendances if a.clock_out is None]
    working_user_ids = {a.user_id for a in working_atts}

    # Active table sessions
    active_sessions = list(
        TableSession.objects.filter(
            table__shop=shop,
            start_time__date=view_date,
            end_time__isnull=True,
        ).select_related('user', 'table', 'attendance').order_by('start_time')
    )
    active_session_user_ids = {s.user_id for s in active_sessions}

    # Idle = working but not in any table session
    idle_atts = [a for a in working_atts if a.user_id not in active_session_user_ids]

    # Not yet clocked in
    clocked_in_ids = {a.user_id for a in day_attendances}
    not_clocked_in = [u for u in all_staff if u.id not in clocked_in_ids]

    # Completed table sessions
    completed_sessions = list(
        TableSession.objects.filter(
            table__shop=shop,
            start_time__date=view_date,
            end_time__isnull=False,
        ).select_related('user', 'table').order_by('-end_time')
    )

    # Annotate durations
    for att in working_atts:
        delta = now - att.clock_in
        h, rem = divmod(int(delta.total_seconds()), 3600)
        att.duration_str = f'{h}h{rem // 60:02d}m'

    for sess in active_sessions:
        delta = now - sess.start_time
        h, rem = divmod(int(delta.total_seconds()), 3600)
        sess.duration_str = f'{h}h{rem // 60:02d}m'

    for sess in completed_sessions:
        delta = sess.end_time - sess.start_time
        h, rem = divmod(int(delta.total_seconds()), 3600)
        sess.duration_str = f'{h}h{rem // 60:02d}m'

    # Date navigation
    prev_date = view_date - datetime.timedelta(days=1)
    next_date = view_date + datetime.timedelta(days=1)

    # Pending corrections (全部待審核，不限日期)
    pending_corrections = list(
        Attendance.objects.filter(
            user__shop=shop,
            status=Attendance.Status.PENDING_CORRECTION,
        ).select_related('user').order_by('-clock_in')
    )

    context = {
        'shop': shop,
        'view_date': view_date,
        'today': today,
        'is_today': view_date == today,
        'prev_date': prev_date,
        'next_date': next_date,
        'all_staff_count': all_staff.count(),
        'working_atts': working_atts,
        'active_sessions': active_sessions,
        'idle_atts': idle_atts,
        'not_clocked_in': not_clocked_in,
        'completed_sessions': completed_sessions,
        'clocked_out_atts': clocked_out_atts,
        'working_count': len(working_atts),
        'active_count': len(active_sessions),
        'idle_count': len(idle_atts),
        'absent_count': len(not_clocked_in),
        'pending_corrections': pending_corrections,
        'pending_count': len(pending_corrections),
    }
    return render(request, 'agent/daily.html', context)


@agent_required
def agent_clock_employee(request):
    """Agent 替員工打上班 / 下班卡。"""
    if request.method != 'POST':
        return redirect('agent_daily')

    shop = _get_agent_shop(request.user)
    employee_id = request.POST.get('employee_id')
    action = request.POST.get('action')

    employee = get_object_or_404(User, id=employee_id, shop=shop)
    today = timezone.localdate()
    now = timezone.now()

    # 允許手動調整時間
    time_str = request.POST.get('clock_time', '').strip()
    if time_str:
        try:
            custom_time = datetime.time.fromisoformat(time_str)
            now = timezone.make_aware(datetime.datetime.combine(today, custom_time))
        except ValueError:
            pass

    name = employee.get_full_name() or employee.username

    if action == 'clock_in':
        existing = Attendance.objects.filter(
            user=employee, clock_in__date=today, clock_out__isnull=True, status='normal'
        ).first()
        if existing:
            messages.warning(request, f'{name} 已打上班卡')
        else:
            segment = int(request.POST.get('segment', 1))
            Attendance.objects.create(user=employee, clock_in=now, work_segment=segment)
            messages.success(request, f'{name} 上班打卡成功 ({timezone.localtime(now).strftime("%H:%M")})')

    elif action == 'clock_out':
        att = Attendance.objects.filter(
            user=employee, clock_in__date=today, clock_out__isnull=True, status='normal'
        ).first()
        if att:
            TableSession.objects.filter(user=employee, end_time__isnull=True).update(end_time=now)
            att.clock_out = now
            att.save()
            messages.success(request, f'{name} 下班打卡成功')
        else:
            messages.warning(request, f'{name} 沒有進行中的上班記錄')

    return redirect('agent_daily')


@agent_required
def agent_assign_table(request):
    """分配員工到桌次。"""
    shop = _get_agent_shop(request.user)
    today = timezone.localdate()

    working_atts = Attendance.objects.filter(
        user__shop=shop,
        clock_in__date=today,
        clock_out__isnull=True,
        status='normal',
    ).select_related('user').order_by('user__employee_code')

    tables = Table.objects.filter(shop=shop, is_active=True).order_by('name')
    preselect_employee = request.GET.get('employee_id', '')

    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        table_id = request.POST.get('table_id')
        start_time_str = request.POST.get('start_time', '').strip()

        att = Attendance.objects.filter(
            user_id=employee_id, user__shop=shop,
            clock_in__date=today, clock_out__isnull=True, status='normal'
        ).first()
        if not att:
            messages.error(request, '找不到該員工的今日出勤記錄')
            return redirect('agent_assign_table')

        table = get_object_or_404(Table, id=table_id, shop=shop)

        # 結束此員工現有進行中的桌次
        TableSession.objects.filter(user_id=employee_id, end_time__isnull=True).update(end_time=timezone.now())

        start_time = timezone.now()
        if start_time_str:
            try:
                custom_time = datetime.time.fromisoformat(start_time_str)
                start_time = timezone.make_aware(datetime.datetime.combine(today, custom_time))
            except ValueError:
                pass

        TableSession.objects.create(
            table=table, user_id=employee_id, attendance=att, start_time=start_time,
        )
        name = att.user.get_full_name() or att.user.username
        messages.success(request, f'{name} 已安排至 {table.name}')
        return redirect('agent_daily')

    context = {
        'shop': shop,
        'working_atts': working_atts,
        'tables': tables,
        'preselect_employee': preselect_employee,
        'today': today,
    }
    return render(request, 'agent/assign_table.html', context)


@agent_required
def agent_end_session(request, session_id):
    """結束桌次服務。"""
    if request.method != 'POST':
        return redirect('agent_daily')

    shop = _get_agent_shop(request.user)
    session = get_object_or_404(TableSession, id=session_id, table__shop=shop, end_time__isnull=True)

    now = timezone.now()
    end_time_str = request.POST.get('end_time', '').strip()
    if end_time_str:
        try:
            custom_time = datetime.time.fromisoformat(end_time_str)
            now = timezone.make_aware(datetime.datetime.combine(timezone.localdate(), custom_time))
        except ValueError:
            pass

    session.end_time = now
    session.save()

    delta = session.end_time - session.start_time
    h, rem = divmod(int(delta.total_seconds()), 3600)
    name = session.user.get_full_name() or session.user.username
    messages.success(request, f'{name} 在 {session.table.name} 服務結束，工時 {h}h{rem // 60:02d}m')
    return redirect('agent_daily')


@agent_required
def agent_monthly(request):
    user = request.user
    shop = _get_agent_shop(user)
    today = timezone.localdate()

    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    all_staff = User.objects.filter(shop=shop, role='staff', is_active=True).order_by('employee_code')
    work_modes = WorkMode.objects.filter(shop=shop).prefetch_related('users')

    staff_stats = []
    for staff in all_staff:
        month_atts = list(Attendance.objects.filter(
            user=staff, clock_in__year=year, clock_in__month=month,
            status__in=['normal', 'approved'],
        ))
        work_days = len({a.clock_in.date() for a in month_atts})
        total_hours = round(sum(a.duration_hours or 0 for a in month_atts), 1)

        table_sessions = list(TableSession.objects.filter(
            user=staff, start_time__year=year, start_time__month=month, end_time__isnull=False,
        ))
        table_count = len(table_sessions)
        table_hours = round(sum(
            (s.end_time - s.start_time).total_seconds() / 3600 for s in table_sessions
        ), 1)

        work_mode = staff.work_modes.filter(shop=shop).first()
        expected_hours = float(work_mode.total_hours) if work_mode else None
        anomaly = expected_hours is not None and total_hours < expected_hours * 0.8

        staff_stats.append({
            'user': staff,
            'work_days': work_days,
            'total_hours': total_hours,
            'table_count': table_count,
            'table_hours': table_hours,
            'expected_hours': expected_hours,
            'anomaly': anomaly,
            'work_mode': work_mode,
        })

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    context = {
        'shop': shop,
        'staff_stats': staff_stats,
        'work_modes': work_modes,
        'year': year, 'month': month,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'today': today,
        'is_current_month': (year == today.year and month == today.month),
    }
    return render(request, 'agent/monthly.html', context)


@agent_required
def agent_add_employee(request):
    """新增員工。"""
    shop = _get_agent_shop(request.user)

    if request.method == 'POST':
        employee_code = request.POST.get('employee_code', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        work_mode_id = request.POST.get('work_mode_id', '')

        if not username or not password or not first_name:
            messages.error(request, '帳號、姓名與密碼為必填')
            return redirect('agent_monthly')

        if User.objects.filter(username=username).exists():
            messages.error(request, f'帳號 {username} 已存在')
            return redirect('agent_monthly')

        from django.contrib.auth.models import Group
        staff_user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            role='staff',
            shop=shop,
            employee_code=employee_code,
        )
        staff_user.groups.add(Group.objects.get(name='Staff'))

        if work_mode_id:
            try:
                mode = WorkMode.objects.get(id=work_mode_id, shop=shop)
                mode.users.add(staff_user)
            except WorkMode.DoesNotExist:
                pass

        messages.success(request, f'員工 {first_name}（{username}）已新增')
        return redirect('agent_monthly')

    return redirect('agent_monthly')


@agent_required
def agent_approve_correction(request, attendance_id):
    """審核補簽申請（核准 / 拒絕）。"""
    if request.method != 'POST':
        return redirect('agent_corrections')

    shop = _get_agent_shop(request.user)
    att = get_object_or_404(
        Attendance, id=attendance_id,
        user__shop=shop, status=Attendance.Status.PENDING_CORRECTION
    )

    action = request.POST.get('action')
    name = att.user.get_full_name() or att.user.username

    if action == 'approve':
        # 允許 agent 調整核准的時間
        for field, time_key in [('clock_in', 'approved_clock_in'), ('clock_out', 'approved_clock_out')]:
            time_str = request.POST.get(time_key, '').strip()
            if time_str:
                try:
                    custom_time = datetime.time.fromisoformat(time_str)
                    current_val = getattr(att, field)
                    if current_val:
                        new_dt = timezone.make_aware(
                            datetime.datetime.combine(current_val.date(), custom_time)
                        )
                        setattr(att, field, new_dt)
                except ValueError:
                    pass
        att.status = Attendance.Status.APPROVED
        att.save()
        messages.success(request, f'{name} 的補簽已核准')

    elif action == 'reject':
        att.status = Attendance.Status.REJECTED
        att.save()
        messages.warning(request, f'{name} 的補簽已拒絕')

    return redirect('agent_corrections')


@agent_required
def agent_corrections(request):
    """補簽審核列表。"""
    shop = _get_agent_shop(request.user)

    pending = list(
        Attendance.objects.filter(
            user__shop=shop,
            status=Attendance.Status.PENDING_CORRECTION,
        ).select_related('user').order_by('-clock_in')
    )

    # 最近 14 天已處理的記錄
    cutoff = timezone.now() - datetime.timedelta(days=14)
    resolved = list(
        Attendance.objects.filter(
            user__shop=shop,
            status__in=[Attendance.Status.APPROVED, Attendance.Status.REJECTED],
            clock_in__gte=cutoff,
        ).select_related('user').order_by('-clock_in')[:30]
    )

    # 標記補簽類型
    for att in pending + resolved:
        att.correction_type_label = '補打下班卡' if att.clock_out else '補打上班卡'

    context = {
        'shop': shop,
        'pending': pending,
        'resolved': resolved,
    }
    return render(request, 'agent/corrections.html', context)


@agent_required
def agent_correction_detail(request, attendance_id):
    """補簽申請詳情 — 查看証明圖片並審核。"""
    shop = _get_agent_shop(request.user)
    att = get_object_or_404(Attendance, id=attendance_id, user__shop=shop)
    att.correction_type_label = '補打下班卡' if att.clock_out else '補打上班卡'

    context = {
        'shop': shop,
        'att': att,
        'is_pending': att.status == Attendance.Status.PENDING_CORRECTION,
    }
    return render(request, 'agent/correction_detail.html', context)


# ─────────────────────────────────────────────
# Profile (all roles)
# ─────────────────────────────────────────────
@login_required
def profile_view(request):
    """個人資料 — 修改姓名與密碼，所有角色皆可使用。"""
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_name':
            first_name = request.POST.get('first_name', '').strip()
            if first_name:
                user.first_name = first_name
                user.save(update_fields=['first_name'])
                messages.success(request, '姓名已更新')
            else:
                messages.error(request, '姓名不可為空')

        elif action == 'change_password':
            current = request.POST.get('current_password', '')
            new_pw = request.POST.get('new_password', '')
            confirm = request.POST.get('confirm_password', '')

            if not user.check_password(current):
                messages.error(request, '目前密碼不正確')
            elif len(new_pw) < 8:
                messages.error(request, '新密碼至少需要 8 個字元')
            elif new_pw != confirm:
                messages.error(request, '兩次輸入的新密碼不一致')
            else:
                user.set_password(new_pw)
                user.save()
                # 密碼更改後重新登入，避免 session 失效
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, '密碼已成功更新')

        return redirect('profile')

    return render(request, 'profile.html', {'user': user})


# ─────────────────────────────────────────────
# Mami Views
# ─────────────────────────────────────────────
def mami_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role not in ('mami', 'admin') and not request.user.is_superuser:
            messages.error(request, '您沒有 Mami 管理權限')
            return redirect('agent_daily')
        return view_func(request, *args, **kwargs)
    return wrapper


@mami_required
def mami_employee_detail(request, user_id):
    """單一員工詳情：月出勤、桌次、薪資調整記錄，並可新增調整。"""
    shop = _get_agent_shop(request.user)
    employee = get_object_or_404(User, id=user_id, shop=shop)
    today = timezone.localdate()

    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    if request.method == 'POST':
        entry_type = request.POST.get('type', '').strip()
        amount_str = request.POST.get('amount', '').strip()
        description = request.POST.get('description', '').strip()
        date_str = request.POST.get('date', str(today))

        if not (entry_type and amount_str and description):
            messages.error(request, '請填寫所有必填欄位')
        else:
            try:
                amount = Decimal(amount_str)
                entry_date = datetime.date.fromisoformat(date_str)
                SalaryDamage.objects.create(
                    user=employee, type=entry_type,
                    amount=amount, description=description, date=entry_date,
                )
                messages.success(request, '薪資調整記錄已新增')
            except (ValueError, InvalidOperation):
                messages.error(request, '金額格式不正確')
        return redirect(f'/mami/employee/{user_id}/?year={year}&month={month}')

    # 月出勤
    month_atts = list(Attendance.objects.filter(
        user=employee, clock_in__year=year, clock_in__month=month,
        status__in=['normal', 'approved'],
    ).order_by('-clock_in'))
    work_days = len({a.clock_in.date() for a in month_atts})
    total_hours = round(sum(a.duration_hours or 0 for a in month_atts), 1)

    # 桌次
    table_sessions = list(TableSession.objects.filter(
        user=employee, start_time__year=year, start_time__month=month,
    ).select_related('table').order_by('-start_time'))
    for s in table_sessions:
        if s.end_time:
            delta = s.end_time - s.start_time
            h, rem = divmod(int(delta.total_seconds()), 3600)
            s.duration_str = f'{h}h{rem // 60:02d}m'
        else:
            s.duration_str = '進行中'

    # 薪資調整
    salary_records = list(SalaryDamage.objects.filter(
        user=employee, date__year=year, date__month=month,
    ).order_by('-date'))
    salary_add = sum(r.amount for r in salary_records if r.type == 'salary_add')
    salary_deduct = sum(r.amount for r in salary_records if r.type in ('salary_deduct', 'damage'))

    work_mode = employee.work_modes.filter(shop=shop).first()
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    context = {
        'shop': shop, 'employee': employee,
        'year': year, 'month': month,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'is_current_month': (year == today.year and month == today.month),
        'month_atts': month_atts,
        'work_days': work_days, 'total_hours': total_hours,
        'table_sessions': table_sessions,
        'salary_records': salary_records,
        'salary_add': salary_add, 'salary_deduct': salary_deduct,
        'work_mode': work_mode, 'today': today,
        'entry_types': SalaryDamage.EntryType.choices,
    }
    return render(request, 'mami/employee_detail.html', context)


@mami_required
def mami_salary(request):
    """全店薪資調整總覽：月份篩選、員工篩選、新增記錄。"""
    shop = _get_agent_shop(request.user)
    today = timezone.localdate()

    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    employee_id = request.GET.get('employee_id', '')

    all_staff = User.objects.filter(shop=shop, is_active=True).order_by('employee_code', 'first_name')

    if request.method == 'POST':
        emp_id = request.POST.get('employee_id', '').strip()
        entry_type = request.POST.get('type', '').strip()
        amount_str = request.POST.get('amount', '').strip()
        description = request.POST.get('description', '').strip()
        date_str = request.POST.get('date', str(today))

        if not (emp_id and entry_type and amount_str and description):
            messages.error(request, '請填寫所有必填欄位')
        else:
            try:
                emp = get_object_or_404(User, id=emp_id, shop=shop)
                amount = Decimal(amount_str)
                entry_date = datetime.date.fromisoformat(date_str)
                SalaryDamage.objects.create(
                    user=emp, type=entry_type,
                    amount=amount, description=description, date=entry_date,
                )
                messages.success(request, f'{emp.get_full_name() or emp.username} 薪資記錄已新增')
            except (ValueError, InvalidOperation):
                messages.error(request, '金額格式不正確')
        return redirect(f'/mami/salary/?year={year}&month={month}')

    records_qs = SalaryDamage.objects.filter(
        user__shop=shop, date__year=year, date__month=month,
    ).select_related('user').order_by('-date', 'user__employee_code')

    if employee_id:
        records_qs = records_qs.filter(user_id=employee_id)

    records = list(records_qs)
    total_add = sum(r.amount for r in records if r.type == 'salary_add')
    total_deduct = sum(r.amount for r in records if r.type in ('salary_deduct', 'damage'))

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    context = {
        'shop': shop, 'all_staff': all_staff,
        'year': year, 'month': month,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'is_current_month': (year == today.year and month == today.month),
        'employee_id': employee_id,
        'records': records,
        'total_add': total_add, 'total_deduct': total_deduct,
        'entry_types': SalaryDamage.EntryType.choices,
        'today': today,
    }
    return render(request, 'mami/salary.html', context)


@mami_required
def mami_salary_delete(request, salary_id):
    """刪除薪資調整記錄。"""
    if request.method != 'POST':
        return redirect('mami_salary')
    shop = _get_agent_shop(request.user)
    record = get_object_or_404(SalaryDamage, id=salary_id, user__shop=shop)
    record.delete()
    messages.success(request, '記錄已刪除')
    return redirect('mami_salary')
