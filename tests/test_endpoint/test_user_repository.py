"""
Unit tests for the UserRepository class.

This module tests pagination queries, search and filtering functionality,
and query performance with mock large datasets.

Requirements tested:
- 2.1: Improved User List and Search Endpoints
- 2.2: Enhanced User Statistics and Analytics  
- 6.1: Optimized Database Queries and Performance
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from sqlalchemy import func

from repositories.user_repository import UserRepository, UserFilters, SortConfig
from models import User, UserRole, UserPoint, PointTransaction, UserProviderPermission


class TestUserRepositoryPagination:
    """Test pagination functionality of UserRepository."""
    
    def test_get_users_with_pagination_basic(self, db_session):
        """Test basic pagination with default parameters."""
        # Create test users
        users = []
        for i in range(15):
            user = User(
                id=f"user{i:06d}",
                username=f"testuser{i}",
                email=f"test{i}@example.com",
                hashed_password=f"hashed_pass_{i}",
                role=UserRole.GENERAL_USER,
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        # Test pagination
        repo = UserRepository(db_session)
        filters = UserFilters()
        sort_config = SortConfig(sort_by="created_at", sort_order="desc")
        
        # First page
        page1_users, total = repo.get_users_with_pagination(
            page=1, limit=5, filters=filters, sort_config=sort_config
        )
        
        assert len(page1_users) == 5
        assert total == 15
        
        # Second page
        page2_users, total = repo.get_users_with_pagination(
            page=2, limit=5, filters=filters, sort_config=sort_config
        )
        
        assert len(page2_users) == 5
        assert total == 15
        
        # Third page
        page3_users, total = repo.get_users_with_pagination(
            page=3, limit=5, filters=filters, sort_config=sort_config
        )
        
        assert len(page3_users) == 5
        assert total == 15
        
        # Fourth page (partial)
        page4_users, total = repo.get_users_with_pagination(
            page=4, limit=5, filters=filters, sort_config=sort_config
        )
        
        assert len(page4_users) == 0  # No more users
        assert total == 15
    
    def test_pagination_with_different_page_sizes(self, db_session):
        """Test pagination with various page sizes."""
        # Create 20 test users
        users = []
        for i in range(20):
            user = User(
                id=f"page{i:06d}",
                username=f"pageuser{i}",
                email=f"page{i}@example.com",
                hashed_password=f"hashed_pass_{i}",
                role=UserRole.GENERAL_USER
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        repo = UserRepository(db_session)
        filters = UserFilters()
        sort_config = SortConfig()
        
        # Test different page sizes
        test_cases = [
            (1, 10, 10),  # page, limit, expected_count
            (2, 10, 10),
            (3, 10, 0),   # No more results
            (1, 25, 20),  # Larger page size
            (1, 5, 5),    # Smaller page size
            (4, 5, 5),    # Fourth page with small size
            (5, 5, 0),    # Beyond available data
        ]
        
        for page, limit, expected_count in test_cases:
            result_users, total = repo.get_users_with_pagination(
                page=page, limit=limit, filters=filters, sort_config=sort_config
            )
            
            assert len(result_users) == expected_count, f"Page {page}, limit {limit}: expected {expected_count}, got {len(result_users)}"
            assert total == 20, f"Total should always be 20, got {total}"
    
    def test_pagination_edge_cases(self, db_session):
        """Test pagination edge cases."""
        # Create 3 test users
        users = []
        for i in range(3):
            user = User(
                id=f"edge{i:06d}",
                username=f"edgeuser{i}",
                email=f"edge{i}@example.com",
                hashed_password=f"hashed_pass_{i}",
                role=UserRole.GENERAL_USER
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        repo = UserRepository(db_session)
        filters = UserFilters()
        sort_config = SortConfig()
        
        # Test edge cases
        edge_cases = [
            (0, 5),    # Page 0 should be treated as page 1
            (-1, 5),   # Negative page should be treated as page 1
            (1, 0),    # Zero limit should be handled gracefully
            (1, -5),   # Negative limit should be handled gracefully
            (100, 5),  # Very high page number
        ]
        
        for page, limit in edge_cases:
            try:
                result_users, total = repo.get_users_with_pagination(
                    page=page, limit=limit, filters=filters, sort_config=sort_config
                )
                # Should not raise an exception
                assert total == 3
                assert isinstance(result_users, list)
            except Exception as e:
                pytest.fail(f"Pagination failed for page={page}, limit={limit}: {e}")
    
    def test_pagination_with_sorting(self, db_session):
        """Test pagination with different sorting options."""
        # Create users with different attributes for sorting
        users = [
            User(id="sort001", username="zebra", email="z@example.com", hashed_password="pass", 
                 role=UserRole.GENERAL_USER, created_at=datetime.utcnow() - timedelta(days=1)),
            User(id="sort002", username="alpha", email="a@example.com", hashed_password="pass", 
                 role=UserRole.ADMIN_USER, created_at=datetime.utcnow() - timedelta(days=2)),
            User(id="sort003", username="beta", email="b@example.com", hashed_password="pass", 
                 role=UserRole.SUPER_USER, created_at=datetime.utcnow() - timedelta(days=3)),
        ]
        
        db_session.add_all(users)
        db_session.commit()
        
        repo = UserRepository(db_session)
        filters = UserFilters()
        
        # Test sorting by username ascending
        sort_config = SortConfig(sort_by="username", sort_order="asc")
        sorted_users, total = repo.get_users_with_pagination(
            page=1, limit=10, filters=filters, sort_config=sort_config
        )
        
        assert len(sorted_users) == 3
        assert sorted_users[0].username == "alpha"
        assert sorted_users[1].username == "beta"
        assert sorted_users[2].username == "zebra"
        
        # Test sorting by username descending
        sort_config = SortConfig(sort_by="username", sort_order="desc")
        sorted_users, total = repo.get_users_with_pagination(
            page=1, limit=10, filters=filters, sort_config=sort_config
        )
        
        assert sorted_users[0].username == "zebra"
        assert sorted_users[1].username == "beta"
        assert sorted_users[2].username == "alpha"
        
        # Test sorting by created_at
        sort_config = SortConfig(sort_by="created_at", sort_order="desc")
        sorted_users, total = repo.get_users_with_pagination(
            page=1, limit=10, filters=filters, sort_config=sort_config
        )
        
        # Most recent first (sort001 was created 1 day ago, most recent)
        assert sorted_users[0].id == "sort001"
        assert sorted_users[1].id == "sort002"
        assert sorted_users[2].id == "sort003"


class TestUserRepositorySearch:
    """Test search functionality of UserRepository."""
    
    def test_search_users_by_username(self, db_session):
        """Test searching users by username."""
        # Create test users with specific usernames
        users = [
            User(id="search01", username="john_doe", email="john@example.com", hashed_password="pass"),
            User(id="search02", username="jane_smith", email="jane@example.com", hashed_password="pass"),
            User(id="search03", username="john_admin", email="admin@example.com", hashed_password="pass"),
            User(id="search04", username="bob_jones", email="bob@example.com", hashed_password="pass"),
        ]
        
        db_session.add_all(users)
        db_session.commit()
        
        repo = UserRepository(db_session)
        
        # Search for "john" - should find john_doe and john_admin
        results = repo.search_users("john", limit=10)
        assert len(results) == 2
        usernames = [user.username for user in results]
        assert "john_doe" in usernames
        assert "john_admin" in usernames
        
        # Search for "jane" - should find jane_smith
        results = repo.search_users("jane", limit=10)
        assert len(results) == 1
        assert results[0].username == "jane_smith"
        
        # Search for "xyz" - should find nothing
        results = repo.search_users("xyz", limit=10)
        assert len(results) == 0
    
    def test_search_users_by_email(self, db_session):
        """Test searching users by email."""
        users = [
            User(id="email01", username="user1", email="test@company.com", hashed_password="pass"),
            User(id="email02", username="user2", email="admin@company.com", hashed_password="pass"),
            User(id="email03", username="user3", email="user@different.org", hashed_password="pass"),
        ]
        
        db_session.add_all(users)
        db_session.commit()
        
        repo = UserRepository(db_session)
        
        # Search by domain
        results = repo.search_users("company.com", limit=10)
        assert len(results) == 2
        
        # Search by specific email
        results = repo.search_users("admin@company.com", limit=10)
        assert len(results) == 1
        assert results[0].email == "admin@company.com"
        
        # Search by partial email
        results = repo.search_users("different", limit=10)
        assert len(results) == 1
        assert results[0].email == "user@different.org"
    
    def test_search_case_insensitive(self, db_session):
        """Test that search is case insensitive."""
        users = [
            User(id="case01", username="TestUser", email="Test@Example.COM", hashed_password="pass"),
            User(id="case02", username="ADMIN", email="ADMIN@SITE.ORG", hashed_password="pass"),
        ]
        
        db_session.add_all(users)
        db_session.commit()
        
        repo = UserRepository(db_session)
        
        # Test lowercase search
        results = repo.search_users("testuser", limit=10)
        assert len(results) == 1
        assert results[0].username == "TestUser"
        
        # Test uppercase search
        results = repo.search_users("ADMIN", limit=10)
        assert len(results) == 1
        assert results[0].username == "ADMIN"
        
        # Test mixed case search
        results = repo.search_users("ExAmPlE", limit=10)
        assert len(results) == 1
        assert results[0].email == "Test@Example.COM"
    
    def test_search_with_limit(self, db_session):
        """Test search with result limits."""
        # Create many users with similar names
        users = []
        for i in range(20):
            user = User(
                id=f"limit{i:03d}",
                username=f"testuser{i}",
                email=f"test{i}@example.com",
                hashed_password="pass"
            )
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        repo = UserRepository(db_session)
        
        # Search with different limits
        results = repo.search_users("testuser", limit=5)
        assert len(results) == 5
        
        results = repo.search_users("testuser", limit=15)
        assert len(results) == 15
        
        results = repo.search_users("testuser", limit=50)
        assert len(results) == 20  # Only 20 users exist
    
    def test_search_empty_query(self, db_session):
        """Test search with empty or None query."""
        # Create some users
        users = [
            User(id="empty01", username="user1", email="user1@example.com", hashed_password="pass"),
            User(id="empty02", username="user2", email="user2@example.com", hashed_password="pass"),
        ]
        
        db_session.add_all(users)
        db_session.commit()
        
        repo = UserRepository(db_session)
        
        # Test empty string
        results = repo.search_users("", limit=10)
        assert len(results) == 0
        
        # Test None
        results = repo.search_users(None, limit=10)
        assert len(results) == 0
        
        # Test whitespace only
        results = repo.search_users("   ", limit=10)
        assert len(results) == 0


class TestUserRepositoryFiltering:
    """Test filtering functionality of UserRepository."""
    
    def test_filter_by_role(self, db_session):
        """Test filtering users by role."""
        users = [
            User(id="role01", username="super1", email="super1@example.com", hashed_password="pass", role=UserRole.SUPER_USER),
            User(id="role02", username="admin1", email="admin1@example.com", hashed_password="pass", role=UserRole.ADMIN_USER),
            User(id="role03", username="admin2", email="admin2@example.com", hashed_password="pass", role=UserRole.ADMIN_USER),
            User(id="role04", username="user1", email="user1@example.com", hashed_password="pass", role=UserRole.GENERAL_USER),
            User(id="role05", username="user2", email="user2@example.com", hashed_password="pass", role=UserRole.GENERAL_USER),
        ]
        
        db_session.add_all(users)
        db_session.commit()
        
        repo = UserRepository(db_session)
        sort_config = SortConfig()
        
        # Filter by SUPER_USER
        filters = UserFilters(role=UserRole.SUPER_USER)
        filtered_users, total = repo.get_users_with_pagination(
            page=1, limit=10, filters=filters, sort_config=sort_config
        )
        assert len(filtered_users) == 1
        assert total == 1
        assert filtered_users[0].role == UserRole.SUPER_USER
        
        # Filter by ADMIN_USER
        filters = UserFilters(role=UserRole.ADMIN_USER)
        filtered_users, total = repo.get_users_with_pagination(
            page=1, limit=10, filters=filters, sort_config=sort_config
        )
        assert len(filtered_users) == 2
        assert total == 2
        assert all(user.role == UserRole.ADMIN_USER for user in filtered_users)
        
        # Filter by GENERAL_USER
        filters = UserFilters(role=UserRole.GENERAL_USER)
        filtered_users, total = repo.get_users_with_pagination(
            page=1, limit=10, filters=filters, sort_config=sort_config
        )
        assert len(filtered_users) == 2
        asse= 02_ids)) =n(page.intersectioge1_idsert len(pa    ass    s_page2}
userr in  useuser.id fors = {page2_id        rs_page1}
usein  for user = {user.idpage1_ids es
        tween pagbe overlap erify no# V     
            not None
rsor2 is next_cu   assert
     == 5) rs_page2 len(use    assert     
             )
 
 ext_cursor_id=norurs    c    
    =True,nationpagior_   use_curs
         nfig,rt_cog=sort_confi         so   ,
filterss=    filter
           limit=5,  =1,
       ge        pa   
 asets(arge_datry_for_le_queepo.optimizcursor2 = rxt_al, ne totusers_page2,  sor
      using curnext page  Get 
        #     
   ot Nonersor is nrt next_cu  asse      ate total
lculoesn't caion dsor paginat1  # Cur total == -sert       as== 5
 sers_page1)  len(ussert        a    
     )
    
   =Truepaginatione_cursor_   us     fig,
    ort_conrt_config=s       so
     ters,ers=fililt  f
           limit=5,          
 1,e=    pag  ts(
      selarge_datafor_e_query_.optimizepoor = r_cursl, next totausers_page1,        pagination
or-based rs  # Test cu            

  ")="desc sort_orderd_at",="createt_byg(sorrtConfifig = Sort_con       soters()
 rFil= Useers    filtion)
     y(db_sessserRepositor Upo =re        
        
mmit()sion.co   db_ses
     users)dd_all(ssion.a     db_se
   r)
        used(rs.appen    use    
       )  =i)
       lta(minutestimedeutcnow() - atetime.eated_at=d         cr    pass",
   assword="hed_pas           h,
     ple.com"xamr{i}@el=f"curso   emai            ser{i}",
 =f"cursorusername     u           3d}",
cursor{i:0  id=f"            
  ser(  user = U         ge(20):
  in ran  for i
      users = []Ds
        able I predictt users withte tesea Cr       #"
 .""setslarge datan for atiod paginr-basersoTest cu""   ":
      db_session)self,tion(_paginaor_cursdatasetsor_large_ize_query_fptimtest_oef  d   
   e
 ctive is Tru.is_aer_usgedt unchan    asserse
    ctive is Fal.is_auser2ted_ert upda        assis False
tive _aced_user1.ispdat   assert u     
     first()
   ulk03")."b.id == lter(Userery(User).fiession.qu_user = db_sgednchan    u()
    ").firstk02bul= "r.id =(Useterer).filquery(Usssion._se = dbpdated_user2
        ust()ulk01").fird == "bUser.ilter(ser).fiery(Ussion.qur1 = db_sepdated_use        us
update Verify      #      
   
  count == 2dated_sert up      as      
  es)
  atpde_users(uatpdrepo.bulk_uted_count = pda u
               
        ]
se},": Fal"is_active", ulk02: "b {"id"           ,
": False}e_activ "is"bulk01",":   {"id          = [
updates s
        ctivate user dea update toulk  # B 
      n)
       (db_sessiorRepositoryepo = Use
        r   mit()
     _session.comdb      sers)
  _all(usion.add  db_ses     
     ]
      
      e=True),is_activs", ord="pasassw hashed_pe.com",@exampl="user3ail em="user3",", username"bulk03r(id=     Usee),
       Tru, is_active="pass"_password=, hashedle.com""user2@examp=", emailme="user2sernak02", user(id="bul         U,
   True)ve=", is_acti="passed_passwordhashe.com", mpl"user1@exa", email=ser1ame="u usernbulk01",er(id="      Us
      = [   users "
     s.""userng multiple updatilk "Test bu   ""):
      db_sessionlf,(seate_userst_bulk_updef tes  
    d + 50
  = 150  # 100nts_sent'] =_50['poit summary     asser1
   ns'] == ioctd_transaeceivey_50['rmmarert su  ass    
  onsacti trans sent# Both'] == 2  nsactionssent_traummary_50['ert s
        ass )
       ys=50m01", daactivity_su"ity_summary(er_activ repo.get_us50 =   summary_   ions)
   transact alludeould inclary (shsummay 0-d Test 5  #  
        nt
    00 seived - 1# 200 rece == 100  nts']t_poi['nesummaryassert 00
        = 2received'] ='points_ummary[  assert s      ] == 100
s_sent'pointry['ma sumsert       as== 2
 sactions'] ['total_tranummary assert sys
        30 daived within# One rece] == 1  ons'transactiived_y['rece summar    assert   
 ayswithin 30 dly one  On # 1 ] ==ions'_transactntummary['set ser       ass == 30
 ys']iod_daummary['perrt s asse  
       
      , days=30)ity_sum01"activry("summavity_actipo.get_user_rery = masum
        ummary0-day s   # Test 3     
     ssion)
   (db_seRepositoryser    repo = U     
      it()
 n.comm  db_sessio    actions)
  ll(transn.add_a db_sessio
       
             ]    ),
         ndow
  e 30-day wi  # Outsid0)elta(days=4w() - timedcnome.uttiated_at=date     cre
           er","transfe=typn_tiosac        tran       0,
 points=5            com",
    @example.eiver2ecail="r_emreceiver              ",
  eiver2"recd=iver_i     rece          ",
 le.comve@exampil="actier_ema        giv
        1",m0tivity_suac giver_id="      
         ction(ansaointTr   P   ),
                 (days=10)
 tadelw() - timecno=datetime.utated_at      cre          ansfer",
_type="trtionsacan       tr    200,
         points=       
     e.com",ampl"active@exeiver_email=  rec             1",
 tivity_sum0r_id="ac     receive        .com",
   ampler@ex"sendel= giver_emai     
          ender123",giver_id="s               tion(
 ansac    PointTr        ,
   )       ys=5)
  medelta(datcnow() - titime.u_at=dateeated cr            
   ",e="transfer_typction  transa           ts=100,
   in        po",
        e.com@exampl"receiver1mail= receiver_e              eiver1",
 id="rec  receiver_             e.com",
 tive@exampl_email="ac     giver         ",
  _sum01="activityiver_id        gn(
        ansactio     PointTr       = [
ions  transacts
       transactionAdd various 
        # )
        (userddn.assiodb_se                )
d="pass"
sworashed_pas           h
 m",ple.coive@examemail="act           
 e_user",tivrname="acse           u01",
 activity_sum="          idser(
      user = U
    y."""ivity summar user actt getting """Tes      ession):
  db_sary(self,mmity_suctiv_get_user_a test  
    defns) == 1
  actionstra.sent_d_userailen(detert le  ass  
    ions) == 1issr_permr.provideed_useetailert len(dass
        nts) == 1r.user_poidetailed_useert len(     asser"
   "detailed_us name ==er_user.usetailed d  assert      one
r is not Ned_usert detail  asse  
      
      tail01")s("deith_detailt_user_wer = repo.ged_usle     detaision)
   sesy(db_tor= UserReposiepo 
        r       t()
 on.commiessi       db_s    
 ion)
    add(transactssion.      db_se)
         ow()
 time.utcn=date created_at           ",
nsferpe="traion_tynsact        tra  nts=100,
      poi     ",
   ple.comxamceiver@eail="receiver_em         re",
   receiver123="eceiver_id      r     e.com",
 mpldetailed@exal="  giver_emai
          ",="detail01ver_id   gi    (
     nsaction PointTration =   transac    s
 ionsact Add tran        #   
n)
     (permissioon.add  db_sessi   )
          er"
 vidtest_proe="provider_nam           01",
 etailer_id="d us           sion(
PermisrovidererPssion = Us    permi    ns
iod permiss       # Ad  
   nts)
    dd(user_poi_session.a db        )
       ints=500
otal_used_po          tts=500,
  inrent_pour           c,
 000tal_points=1          tom",
  ample.co@ex="detailed_email  user         ",
 "detail01d= user_i           UserPoint(
points = r_se u      d points
     # Ad 
    
       add(user)on.db_sessi   
     R
        ).ADMIN_USEole=UserRole  r          "pass",
d=d_passworhashe           ,
 mple.com"xailed@eta"de     email=      ",
 led_user"detaiame=  usern         1",
 ="detail0 id         
  user = User(    data
    ensive ith comprehreate user w    # C"
    .""ed detailsh all relater wit ustting"Test ge  ""n):
      , db_sessios(selfdetailser_with_st_get_u    def te""
    
epository."serRes of U featurest advanced"T""ures:
    atdvancedFesitoryAserRepos TestUlas >= 2


cll_countcount.caquery_.increment_icsmetrry_ock_reposito    assert moo
    s tr statisticlled fo canitoring wasy moerif      # V      
  ics()
  iststatt_user_ = repo.gets      staethod
  stics m stati   # Call 
     
       led()t_calt.asserunent_query_corics.increm_mettorysik_repo        moced
was callnitoring  Verify mo
        #)
                rt_config
onfig=sosort_crs=filters, it=10, filte lim    page=1,
        tion(aginawith_pet_users_ repo.gl =ta  users, to   hod
   nitored met a moall C 
        #
       ortConfig()= Sort_config      srs()
   serFiltes = U   filter)
     b_sessionry(dtoposio = UserRe   rep    
       ommit()
  b_session.c        d
l(users)alsession.add_       db_ 
             ]
  ,
 d="pass")_passworshedom", ha2@example.cmail="user"user2", eusername=02", "monitorid=   User(      
   "),="passrdswopas", hashed_ple.com"user1@examail=, emuser1"me="01", userna"monitor=   User(id[
           users =     est data
  eate some t   # Cr
     """rated.perly integis prong orie monitrformancTest that pe   """
     session):trics, db_mepository_k_reonitor, mocmance_mfor_per(self, mock_integrationonitoringce_mst_performan
    def te_monitor')formanceperpository.ries.user_reositoep @patch('r
   trics')pository_meepository.re_rs.userorieeposit@patch('r
    
    s_time}s" {statok too long:on tolaticalcuistics  f"Stat< 2.0,ats_time    assert stast)
     ould be fgation shgree agabasd (datuld be goonce sho Performa #       
      days
   within 30 eatedll cr # A0 == 100s'] upgn'recent_sitats[assert s0
        '] > istributedts_d'total_poinrt stats[   asse  ctive
   s are aMost user00  # sers'] > 8active_urt stats['   asse000
     s'] == 1tal_usertats['to    assert snable
    e reasoics arfy statist      # Veri  
  
      rt_timee() - stae = time.timats_timst
        statistics()ser_epo.get_u r  stats =e()
      time = time. start_tim  ce
     on performantitics calculastatis   # Test    
        ort time
          imp       

 _session)ory(dbRepositser  repo = U      
   t()
     on.commidb_sessi
        s)pointr_ll(useadd_adb_session.            

    user_point)d(points.appener_ us          )
              + i * 5
d_points=500seotal_u           t   + i * 5,
  =500 rent_points     cur       10,
     s=1000 + i *_point   total        ,
     m"@example.coat{i}il=f"st user_ema       ,
        06d}"rf{i:tat_peid=f"sr_      use   t(
       UserPoinpoint =  user_         s points
  ser hay third uver# E0, 3):  (0, 80geor i in ran f    = []
    tsser_poin
        usersfor many uts Add poin  #  
         )
    (usersd_allssion.ad    db_se  
        
  er)end(us.appsers     u
                )  30 days
 0)  # Last  % 3delta(days=i timeate -_at=base_d  created     
         3% active= 0,  # ~8e=i % 6 !ctiv is_a    
              ),              )
                 RAL_USER
  GENEe UserRole.2 elsf i % 4 == SER iER_UerRole.SUP   Us               e (
       == 1 elsER if i % 4DMIN_USe.AUserRol                  (
   se4 == 0 el i % L_USER if.GENERAole=UserRole           r    
 {i}",s_"hashed_pasword=f_pass  hashed        ",
      ample.comstat{i}@ex email=f"             
  er{i}",tatusername=f"s us       ",
        perf{i:06d} id=f"stat_               er(
   user = Us         nge(1000):
or i in ra f       
        
ow().utcnime datetbase_date =]
          users = [t
      datasege Create a lar # 
       ."""atasetlarge dh a witperformance alculation s c statistic """Test    sion):
   db_seself, t(slarge_datasemance__perfortistics_sta def test
   }s"
    filter_time{date_ong: k too lg tooate filterin, f"Dme < 1.0filter_tiate_assert d  
            _time
  start- e.time() ime = timte_filter_t        da        )
onfig
g=sort_ct_confi, sorlters, filters=fiit=50im, lage=1        p
    _pagination(rs_witho.get_useotal = repte_users, t       da    )
 =10)
    ta(dayselate - timed_dbaseed_before=  creat       =30),
   daysta(el timedate -r=base_ded_afte      creat    s(
  ilter= UserFs       filtere()
  me.timt_time = ti       starng
 lteriate range fi d      # Test  
  }s"
      er_timeed_filtg: {combin lonng took toofilteri"Combined 0, fe < 1.ter_tim_filinedcombert 
        ass   _time
     artme() - sttime.tie = _timed_filter    combin
    )        nfig
sort_cort_config=ers, so=filt filters1, limit=50,       page=on(
     atipaginrs_with_get_usel = repo.sers, totad_uine comb         )
  s=True
       has_point        e=True,
    is_activ        USER,
 GENERAL_=UserRole.    role   ters(
     s = UserFil    filtertime()
    time = time.  start_
      lteringcombined fi Test         #
        
e}s"filter_tim{role_too long:  took iltering0, f"Role ftime < 1.r_le_filtet ro asser
       ers) == 50en(role_ussert l    as  
    time
      t_me() - stare.ti_time = timerrole_filt )
        fig
       ort_conort_config=s, silterslters=ft=50, fipage=1, limi   (
         ationh_paginet_users_wit.gotal = repoe_users, t    rol
    ER)ADMIN_USle.le=UserRoFilters(rors = Userilte       f
 e()me.timme = ti   start_tiing
     e filterol# Test r              
  port time
  im       
   ig()
    rtConfig = Soonf  sort_cion)
      b_sessepository(d= UserR      repo   
  t()
      commi db_session.   oints)
    l(user_p.add_alb_session        d        
nt)
(user_poioints.append    user_p        )
     0
       =50d_pointstal_use to           + i,
    ints=500 nt_po    curre        + i,
    points=1000     total_            .com",
mpleter{i}@exa=f"filil user_ema          
     i:06d}",f{"filter_peruser_id=f                int(
 UserPont =user_poi            oints
s pser ha u Every other # 2): 400,n range(0,   for i i     nts = []
     user_poi
     userss for someAdd point  #     
   rs)
       (use.add_allsessionb_
        d
        r)pend(uses.ap       user
        )      
    100)lta(days=i %ate - timede_at=base_dated         cre    active
   80%   # 5 != 0,_active=i %        is      _USER),
   erRole.SUPER Us else3 == 1SER if i % .ADMIN_UrRolee (Use 0 els if i % 3 ==AL_USERrRole.GENERrole=Use            ",
    ed_pass_{i}"hashpassword=fd_he   has           ,
  ple.com"examer{i}@mail=f"filt      e       ",
   ruser{i}ilte=f"f    username           
 i:06d}",rf{f"filter_pe id=              User(
 er =          us00):
   e(8i in rang     for   
     now()
    tc datetime.uase_date =   b= []
          users    ering
es for filtttribut various ae users with   # Creat""
     t." dataseargece with a lerformanering pest filt   """T     _session):
(self, dbe_datasetce_largrmanrfog_pefilterin   def test_"
    
 time}sarch_main_se{dolong: h took too in searcoma.0, f"De < 1h_tim_searcaindomt     asser5.com
    ainhas dom10th user ery  50  # Ev_results) ==inrt len(doma        asse       
e
 tart_time.time() - sh_time = timain_searc      dom
  100)t= limin5.com",ai"doms(serepo.search_uresults = rin_doma
        e()ime.tim = ttart_timen
        sor domaiearch ft sTes
        # 
        }s"timec_search_fiong: {specih took too larcSpecific se 1.0, f"ime <c_search_t specifi  assert1
      sults) == _relen(specificsert 
        as       e
 - start_tim.time() time = timeific_search_spec       100)
 t=, limiser123"earchu"susers(arch_ = repo.sec_results  specifi     me.time()
 e = ti   start_timrm
     ic ter specif search fo      # Test      
  me}s"
  rch_tiommon_sea {cg:o lonk totoomon search Com", fh_time < 1.0arcmon_se comssert    a  
  lts) == 50mmon_resu len(co     assert
        t_time
    - startime() = time._timeearch common_s    t=100)
   n", limi"commoers(h_us.searc repos =_result     commonme()
    time.tit_time =star        mmon term
earch for co # Test s
       
         time    import  
    on)
      sessiory(db_it= UserRepos    repo  
    ()
       commitession.       db_s)
 ers_all(usaddb_session.  d    
      
    pend(user)sers.ap      u   
          )R
     RAL_USEserRole.GENEle=U ro              ss_{i}",
 shed_pasword=f"hahed_pas     has      
     ,le.com"i}@examp"common{email=f       
         i}",name{"commone=f     usernam         :06d}",
  n{i=f"commo      id   er(
         user = Us       
   ): in range(50for i      rms
  teon search omm with cersd some us    # Ad      
    
  d(user)sers.appen     u  )
                ER
 AL_USRole.GENERrole=User                ",
pass_{i}shed_rd=f"hashed_passwo         ha       omains
nt d differe 100}.com",  #domain{i % 1rch{i}@l=f"seaemai            ",
    r{i}"searchuse username=f               i:06d}",
rf{"search_pe    id=f        ser(
      user = U         0):
 in range(50   for i      []
 rs =        usele content
searchabrs with # Create use
        """ataset.e drgth a la wiancerformarch peest se"T      "":
  ssion), db_se(selfrge_datasetance_laerformarch_pef test_se  
    d"
  e40_time}slong: {pagok too  page to0, f"Deep1.e40_time <  pag      assert"
  e20_time}sng: {pagook too lodle page t"Mid.0, fe < 120_timassert page  }s"
      page1_time long: {ok toopage to"First , f1.0_time < age1   assert pons)
      operatior thesend f 1 seco (less thanreasonable should be Performance       # 
   
       == 1000talrt toasse
        e datad availableyon# Bers) == 0  n(page40_usert le     ass
      me
      - start_titime()ime._time = t40  page   )
          
 g=sort_confifigsort_confilters, filters=it=25,  lim    page=40,      nation(
  agiwith_ps__user repo.getrs, total =sepage40_u      .time()
   = timet_timestar
        tionp paginaTest dee  # 
              == 1000
 rt totalasse    == 25
    rs) ge20_usessert len(pa   a    
     time
    art_me() - stme.ti time =ge20_ti  pa            )
 fig
 ig=sort_cons, sort_conferltlters=fifilimit=25, ge=20,       paon(
      h_paginatirs_wito.get_usereptotal = s, erge20_us pa
       me.time() = tistart_timege
        paest middle      # T       
   0
 l == 100totasert 
        as) == 25_usersrt len(page1   asse      
       t_time
ime() - starme = time.t_ti page1 )
            ig
  sort_config=t_conf, sortersers=fil=25, filte=1, limit        pagon(
    ginatiith_pausers_wepo.get_al = r totsers,     page1_ue()
   time.timime =  start_tst)
        fa be (shouldirst pageTest f        #         
rt time
      impopths
  ent de differatination   # Test pag
          nfig()
    SortCog = confiort_ s
       lters()erFi= Users   filtn)
      essiory(db_sserReposito Upo =
        re    
    commit()on.b_sessi   d
         ch)add_all(batdb_session.         ze]
    batch_sis[i:i +ch = user        batize):
    h_srs), batcn(useange(0, le for i in r100
       h_size =      batc   rformance
or better peches fs in batdd user  # A        
   (user)
   users.append           )
             365)
% lta(days=i () - timedeetime.utcnowd_at=dat    create       
      active # 75%i % 4 != 0, ive= is_act          R,
     e.ADMIN_USERol0 else User% 3 ==  i ER ifNERAL_USrRole.GEle=Use       ro         
pass_{i}",ashed_"hrd=fswo  hashed_pas           .com",
   f{i}@example=f"per  email             er{i}",
 rfuspef"username=             ",
   rf{i:06d}pe   id=f"    
         ser = User(    u   
     nge(1000):for i in ra        ]
rs = [      use
  ingmance testor perfor fsetger dataar# Create a l
        t."""e datasea largrmance with erfo ppaginationst Te      """n):
   db_sessiotaset(self,rge_da_la_performanceaginationst_pf te
    de    "
sets.""large datath mock tory wif UserReposice aspects ot performan   """Tes
 mance:rforryPeepositoserRclass TestU
ey] == 0

t stats[k asser           in stats
ssert key   a   s:
       eyd_kcte key in expe   for       
      ]
 s'
       upt_sign 'recen',_pointsers_with 'us          buted',
 istriints_dl_posers', 'tota 'inactive_ue_users',   'activ
         s',_users', 'general'admin_userper_users', users', 'sual_      'tot  
    ys = [ed_kepectex
        e 0hould batistics s All st
        #     
   atistics()t_user_stpo.ges = re       stat)
 ssionry(db_seerReposito Usrepo =      "
  abase.""y datwith emptatistics "Test st""        _session):
e(self, dbpty_databasemtics_tis_sta_userst_get    def te  
days
  within 7 ed eatnly users cr'] == 2  # Opsnuent_sigts['recassert sta
        s'] == 3al_userstats['totrt sse a 
           s()
   _statistic.get_user= repots ta
        s_session)sitory(dbeporR Usepo =    re          
 .commit()
  db_session      )
 usersall(on.add_ssi db_se 
       ]
             ,
  ys=10))edelta(dadate - time_d_at=bas   create           ", 
   ="passed_password", hashmcoample.1@exl="oldd1", emainame="ol", user"old01   User(id=         ),
ays=5)medelta(d - tise_date_at=ba     created       
     , ass"word="pss_pam", hashed2@example.cont"receemail=ent2", me="recna", userd="recent02 User(i         ),
  ys=2)imedelta(date - tat=base_daeated_ cr            , 
    s"ord="paspassw", hashed_ple.comrecent1@exam", email=""recent1me=, usernaent01"rec User(id="         
    users = [w()
      e.utcnoatetimate = dse_d       ba
 "istics.""atn stalculation it signups cTest recen      """
  ):ionelf, db_sess(snt_signupsreceics_statistr_seet_u def test_g   
   
 ] == 2s'h_pointers_witrt stats['us   asse
     1000 + 2000# == 3000  ributed'] stints_dial_potats['tott ser        ass= 3
] =total_users'ats['assert st     
    ()
       tics_user_statiso.get = rep      statson)
  y(db_sessiepositorpo = UserR  re    
      )
    it(.commssion    db_sents)
    er_poi_all(uson.addb_sessi   d     
      points
    not03 hasint_sta# po           ]
 00),
    d_points=5_usetal=1500, toent_points0, curr00ints=2l_po", tota.comser2@exampleer_email="uust02", ="point_staer_idPoint(us   User
         oints=500),otal_used_p0, t50rent_points=, curs=1000int, total_poample.com"="user1@ex_emailser1", ut0taint_s="pooint(user_id    UserP       ts = [
   user_poin
      r some userspoints fo   # Add      
     ers)
   _all(usaddion.sessb_      d
  ]
        
        ss"),rd="pashed_passwoe.com", ha3@examplseril="uuser3", emame="", usernaat03nt_stoi"p    User(id=       ass"),
 d="pworhed_passe.com", hasmplxa2@e"userr2", email=="useernamet02", uspoint_staid="     User(
       s"),sword="pas hashed_pase.com",r1@exampll="user1", emaiuse username="1","point_stat0(id=      User     s = [
    user
     n.""" informatiog pointudins inclistic user stat"Test   "":
     sion)_sesdbf, ints(selics_with_postatistt_get_user_    def tes
    
 1] ==ctive_users'stats['ina     assert   == 4
 rs'] ['active_usetats   assert s    rs'] == 2
 _uses['generalt statasser 2
        ==_users'] minstats['ad     assert == 1
   sers'] ['super_u statsassert    == 5
     l_users']tart stats['to        asse
        
stics()statiet_user_o.gstats = rep     ssion)
   sitory(db_seUserRepo   repo =  
     
       )it(mmsession.codb_  ers)
      n.add_all(usdb_sessio              

  
        ]rue),=T_active isENERAL_USER,rRole.G   role=Use           
    s",pasd="orshed_passw", haxample.com"user2@e", email=2e="user, usernamt05"r(id="stase U
           ,tive=True), is_acENERAL_USER.Gle=UserRole          ro      ", 
 passpassword=", hashed_xample.com"r1@eseail="uer1", emme="usna", user04statid="     User(    lse),
   ctive=Fa_USER, is_a.ADMINlerRo   role=Use    
          s", d="pashed_passworascom", h@example.l="admin2, emai"admin2"ame=usernat03", er(id="st         Us
   =True), is_activeMIN_USER,ole.ADserR    role=U       ", 
      assord="ppassw", hashed_ple.comadmin1@examemail="1", indm"a username="stat02",   User(id=        ue),
 ctive=TrSER, is_aUPER_UrRole.Sse      role=U
           "pass", ed_password=.com", hash@exampleuper1 email="s1",="superamet01", usern"stad=     User(i
       users = [      n."""
  tiolastics calcu statisic usert ba"Tes       "":
 ession)c(self, db_s_basiatisticsstt_user_gest_    def te"
    
"ository."Rep of Userctionalitytistics funTest sta """s:
   isticStatpositoryRes TestUser
clashn"

_jomin"ad == rname.usesers[0] filtered_u      assert= 1
  tal =t to      asser= 1
  ed_users) =(filteren lsert  as
      min_johnd add only fin     # Shoul 
          )
   g
     rt_conficonfig=sos, sort_s=filter filtert=10, limi  page=1,          gination(
h_pausers_witt_repo.getal = ed_users, tofilter)
        .ADMIN_USERole=UserRolen", rohearch="jers(s UserFiltters =        filr
le filteith admin ron" wfor "joh # Search         
  g()
     onfiig = SortC sort_conf    ssion)
   sitory(db_seRepo= Userpo 
        re     ommit()
   _session.c  db  ers)
    (usion.add_all  db_sess   
         ]
        SER),
  le.ADMIN_UUserRoss", role=rd="passwod_pacom", hashejane@admin., email="admin_jane"ame=" usernch_f03",r(id="sear  Use       
   RAL_USER),ole.GENErole=UserRs", ssword="pasashed_pa", hn@user.coml="johmair_john", ee="useusernam02", arch_fser(id=" Use          _USER),
 INUserRole.ADMe= rol="pass",asswordhashed_pn.com", @admi"john, email=john"min_"adrname= use1",search_f0User(id="        [
      =       users."""
 filterssearch with g combininest ""T"      n):
  b_sessio, dfilters(selfith_ch_wt_sear    def tes"
    
rget "taame ==usern0].tered_users[ssert fil  a  l == 1
     assert tota
       sers) == 1n(filtered_uert less    a
    criteria all matchd shoulcombo01 nly    # O
     
             )config
   g=sort_sort_confilters, =fiiltersit=10, fge=1, lim    pa        (
aginationers_with_p repo.get_ustal =d_users, tolterefi             
 
     )s=7)
     elta(daytimed_date - after=basereated_     c       True,
ctive=        is_a    _USER,
ole.ADMINerR   role=Us       s(
  lterrFirs = Use       filte
 filtersand date tus, , active staombine role        # C        
ig()
nfSortCo = onfig    sort_c)
    sionory(db_sesosit = UserRep     repo    
   ()
    sion.commit   db_ses  ers)
   _all(ussession.add db_   
          
        ])),
  (days=15deltaate - timease_dcreated_at=brue, e=TR, is_activADMIN_USErRole.role=Use               
   ss",assword="pad_pcom", hashexample.oo_old@eil="t, ema"too_old"ername=, usbo04"ser(id="com       U
     ys=2)),imedelta(date - tse_daed_at=balse, creat=Fa is_active_USER,e.ADMIN=UserRolole      r          ss", 
 "pard=woed_pass", hashample.come@exil="inactiv", emaactivee="inam03", usern(id="combo    User       s=3)),
 edelta(dayimte - t=base_daed_atue, creats_active=Tr iER,RAL_USrRole.GENErole=Use               pass", 
  word="ashed_pass", hexample.comle@l="wrong_ro emaing_role",ername="wro", usombo02"c  User(id=       ),
   ys=5)delta(da- timeate ase_dated_at=bcre, tive=TrueSER, is_ac.ADMIN_UserRole    role=U          s", 
   as"password=hed_pascom", hample.arget@ex"temail=, rget"sername="tambo01", user(id="co U       [
    users =         tcnow()
.u= datetimease_date    b
     s."""erple filttiombining mul""Test c"       :
 ession) db_sf,(sel_filterscombineddef test_     2
    
al ==ert tot       assd_active
 r and olseinactive_u 2  # sers) ==tive_u len(inac   assert )
       fig
     t_con_config=sorters, sort=filersfiltmit=10, , li  page=1
          ation(agin_pers_withus.get_repotal =  to_users,active
        in")venactiatus="Iity_st(activerFiltersers = Us    filt days)
     7s in lastnsaction (no trae userster inactiv    # Fil   
    
     ser"_uivee == "actrnam[0].useve_usersert acti        ass= 1
l =rt tota  asse== 1
      ers) e_uslen(activ    assert      )
      config
 g=sort_onfirs, sort_cters=filteimit=10, filge=1, l     paon(
       th_paginati_users_wigetpo. total = reve_users,       acti)
 "Active"ty_status=lters(activirFirs = Use filte    s)
   n last 7 dayctions ih transasers (wit ulter active Fi   #   
     ()
     Config= Sortort_config      sssion)
   se(db_sitoryerRepo= Usepo     r       
  
   ()ssion.commitdb_se        n])
ansactiod_trion, olact_trans([recentallsion.add_ses   db_     
      )
   
       10)ta(days=medelticnow() - e.utt=datetim  created_a         er",
 "transftion_type= transac        50,
   s=oint p           ",
ple.comxam2@eeceiverer_email="r  receiv    
      r456",eiver_id="rec     receive       
mple.com",ld@exaemail="over_   gi      03",
   ="activity   giver_id       (
  iontTransactinsaction = Poanld_tr   oser
     ld_active un for o transactio# Add old
             
     )    s=2)
  medelta(daycnow() - time.utetieated_at=dat     cr     
  transfer",ype="nsaction_t    tra    00,
    points=1            
",ple.comexameiver@rec="ver_email    recei    
    3",12eceiverid="rr_receive          om",
  ample.ctive@exail="ac    giver_em    1",
    "activity0ver_id=      gi    action(
  tTrans = Poinionent_transact   recser
     for active uns t transactio recenAdd
        #      (users)
   _all.add  db_session        
        ]
   s"),
   "password=_pas", hashedcomold@example."", email=tive"old_acsername=ity03", utiv"acr(id=         Use  "),
 ord="passhashed_passwmple.com", xae@eactivil="inr", emaive_useme="inactrna02", usectivity(id="aser           Uass"),
 ssword="p, hashed_pam"xample.co@el="activeemaie_user", "activrname=, use01"vity"actir(id= Use        = [
         users "
  status.""ctivity ers by atering us"Test fil      "":
  ssion)_seus(self, db_stattivityby_acest_filter_
    def t 2
    t total ==   asser
     tsoino por nve 0 e hanonand zero = 2  # t_points) =s_withou len(user    assert )
    ig
       ig=sort_conft_conf, sorrs=filters10, filteit= lim=1,    page
        pagination(ers_with_et_us repo.gnts, total =oihout_pit_wrs       useFalse)
 s_points=(haFiltersters = User  fil      
out pointsthr users wi  # Filte  
      2
      =  = total   assert   0
  nts > _point have curre and poorich== 2  # rith_points)  len(users_wssert
        a       )config
 ort_rt_config=s=filters, so0, filterse=1, limit=1pag            on(
th_paginatisers_wipo.get_uotal = rets, tith_poin     users_wrue)
   points=Tlters(has_ = UserFiilters       fints
 sers with poilter u   # F
            tConfig()
 ig = Sorsort_conf       ssion)
 y(db_serRepositorpo = Use  re
           ommit()
   ion.c     db_sessints)
   (user_po_alladdession.     db_s 
      
    recordt  UserPoin user has no04nts  # poi]
            ts=100),
  l_used_poinotants=0, tnt_poiurreints=100, c total_poample.com",ro@exl="ze_emais03", useroint"p(user_id=UserPoint            ts=90),
l_used_points=10, totaurrent_poinoints=100, cm", total_pe.coxampl="poor@e user_emailpoints02",_id="nt(userrPoi     Use   00),
    ed_points=5l_usota=500, tointsent_pcurr=1000, l_points, totae.com"h@examplricemail="er_ uspoints01","nt(user_id=oiUserP       [
     er_points = 
        use usersr soms fooint Add p        #        

sers)ll(ussion.add_a    db_se     
         ]
   "),
   "passd_password=hashee.com", ne@examplno email="e="none",ernam4", usd="points0r(i     Use,
       "pass")ssword=_pahedcom", hasle.zero@examp, email="e="zero"namts03", userd="poin  User(i         "pass"),
 word=ed_pass", hash@example.comil="poor, ema"poor"=sername, u"points02"id=     User(,
       rd="pass")sswo hashed_pae.com",@examplich email="rich",me="r1", usernaid="points0      User(    rs = [
       use"""
    status.y pointring users b"Test filte "":
       ession)self, db_s_points(r_byst_filte  def te
  ld1"
    rname == "oers[0].usee_us assert rang
       tal == 1rt to       assers) == 1
 usege_len(ranassert 
             )  _config
 rtonfig=so_crs, sortrs=filtelte, fi limit=10     page=1,(
       aginationrs_with_puset_repo.ge=  total s,_user  range
         )     (days=25)
eltaimede_date - tbefore=bas  created_        35),
  ys=a(daedelt timse_date -ed_after=ba  creat          rFilters(
= Users te    file
    ngrain specific reated er users c# Filt
         2
        l ==ert tota        ass 2
d_users) ==ert len(olass    
          )config
  fig=sort_t_con sorfilters,ters=imit=10, fil1, lpage=     
       nation(_pagisers_withpo.get_utal = res, toerusd_
        ol))lta(days=10ate - timedee=base_ded_befors(creat UserFilterers = filtago
       ys re 10 daated before clter users        # Fi
  
      total == 2rt         asse) == 2
ent_usersen(recrt l     asse      )
   _config
  onfig=sortrs, sort_clteers=fit=10, filtge=1, limi     pa      n(
 inatiowith_pag.get_users_ repo total =users,ecent_      r  ys=7))
elta(dadate - timedbase_ter=s(created_afrFilter= Uses  filter
       aysn last 7 d created i users  # Filter     
        ()
 nfigfig = SortCoort_con
        sn)db_sessiopository(= UserReepo 
        r)
        .commit(_session   dbsers)
     n.add_all(ub_sessio
        d              ]
)),
  60ta(days=imedelse_date - t=ba created_at            
     ss",="pawordss_pahedcom", hasple.ery_old@exam"vd", email=_olme="very usernaate04", User(id="d        ys=2)),
   edelta(da- tim_date =basereated_at     c           ", 
 password="ass hashed_ple.com",examp2@centemail="ret2", cenname="re", userdate03"(id=       User=5)),
     elta(days- timede_date t=basreated_a          c
       pass", d="_passworhashede.com", examplcent1@re"l=t1", emaiame="recen, usern="date02"     User(id     ys=30)),
  daimedelta(e - tat=base_datated_         cre   s", 
     d="pased_passworm", hashxample.co="old1@eil1", ema"oldme=, userna01"="date  User(id
            users = [
      w()me.utcnote = datetie_da   bas   e."""
   date rangationcre by ersing ust filter"Tes""
        ssion):_se, dbange(self_rlter_by_datedef test_fi    s)
    
user inactive_in for user _activeis(not user.ssert all   a
      2l == tota    assert   ) == 2
 ctive_usersinalen(rt        asse        )
 fig
ig=sort_conort_confers, sers=filt10, filte=1, limit=       pag     ination(
th_pag_users_wil = repo.gets, totative_usernac  i      ve=False)
_actis(isUserFilters = ilter       fers
 ive uslter inact      # Fi
   )
       _usersactiver in  usee forser.is_activ(u all assert
        total == 2ssert  a   == 2
   _users) ve(actiert len        ass )
      
 ort_configort_config=sfilters, s10, filters=ge=1, limit=        pa   ination(
 ers_with_pagt_uspo.geal = resers, tot active_u     True)
  _active=rs(is = UserFilte     filtersusers
   ter active Fil    #    
    g()
     Config = Sortnfi_co sort      on)
 (db_sessitoryrReposiUse     repo =        
   it()
 commb_session. d     )
  rsdd_all(usesession.adb_         
   ]
     ),
       ve=False, is_acti"ord="passsw hashed_pascom",example.tive2@email="inac", ive2ctername="ina usive02",="inactid    User(    
    ve=False),tiis_acs", "password=, hashed_pasple.com"ve1@examtiemail="inac1", nactivesername="i", u"inactive01User(id=      ),
      tive=Trueass", is_acword="ped_passm", hashample.coctive2@exil="a, emae2""activme=02", usernatived="ac(i  User          =True),
_active is",password="hashed_passle.com", amp"active1@exmail=", e"active1=amesernve01", u(id="acti     User
       users = [      
  """us.active statrs by ring useTest filte"""):
        sionself, db_sesstatus(ctive__aer_bytest_filt
    def users)
    ered_er in filtR for usNERAL_USE UserRole.GEole ==ser.rt all(u    asser    = 2
 total =rt