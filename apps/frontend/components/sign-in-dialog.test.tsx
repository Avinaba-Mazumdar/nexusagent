import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vite-plus/test';
import { SignInDialog } from './sign-in-dialog';

function renderDialog(hasGuestDocuments: boolean) {
    return render(
        <SignInDialog
            open
            onOpenChange={() => {}}
            googleClientId=""
            gisLoaded={false}
            isGoogleLoading={false}
            isGuestLoading={false}
            error={null}
            hasGuestDocuments={hasGuestDocuments}
            onGuestLogin={async () => {}}
            renderGoogleButton={() => {}}
        />
    );
}

describe('SignInDialog', () => {
    it('warns that guest documents are not carried over (R2-UX-04)', () => {
        renderDialog(true);
        expect(screen.getByRole('note')).toHaveTextContent(/documents uploaded as a guest will be deleted/i);
    });

    it('shows no warning without guest documents', () => {
        renderDialog(false);
        expect(screen.queryByRole('note')).not.toBeInTheDocument();
    });
});
